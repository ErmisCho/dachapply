"""TASK-224: what the 40k-token CV request is actually made of, measured without sending it.

The number that started this was the provider's, not ours: LM Studio refused a CV generation with
`request (40654 tokens) exceeds the available context size (32768 tokens)`. That is one number, for
one request, on one day. This command is the reproducible version -- it assembles exactly the prompt
generate_cv_package would build for a job and measures its parts, so the breakdown can be re-read
after any change instead of being a figure somebody wrote down once (AC2).

Nothing here launches a provider and nothing here changes what generation sends (AC6): the prompt is
built with cv_generator's own _prompt/load_candidate_evidence and then thrown away. The only
deliberate deviation is that CODEX_CV_WORKSPACE is blanked for the duration of the evidence load,
because load_candidate_evidence otherwise refreshes a compaction snapshot on the workspace, and a
report has no business writing anything.

Sizes and counts only, never content (AC7). The evidence, the profile notes and the learned
preferences are the owner's personal career data; their LENGTH is the finding, their text is not.
"""
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from jobradar.models import UserProfile
from jobradar.services.access import accessible_jobs
from jobradar.services.cv_generator import (_compact_candidate_evidence, _prompt, _target_names,
                                            applicant_name, detect_job_language,
                                            load_candidate_evidence, user_templates)
from jobradar.services.prompt_builder import build_candidate_profile_text

# generate_cv_package's retry loop, restated here because both constants live inside that function
# body and cannot be imported. tests/test_prompt_size.py reads cv_generator.py and fails if either
# one drifts away from this file.
GENERATION_ATTEMPTS = 3           # cv_generator.py: `for attempt in range(3)`
REPAIR_DIAGNOSTICS_BUDGET = 6000  # cv_generator.py: `failure.diagnostics[-6000:]`
# The block appended to the prompt on attempts 2 and 3, character for character.
REPAIR_BLOCK = ('\n\nAUTOMATIC REPAIR ATTEMPT {attempt}/2:\nThe previous generated documents failed '
                'validation. Read the current copied TeX files, fix the issue below without changing '
                'supported facts, and return complete corrected documents.\n\nFAILURE TO FIX:\n'
                '{summary}\n{diagnostics}')
# The longest summary any RecoverableGenerationError in cv_generator.py carries (line 1099), so the
# retry figures below are a ceiling rather than a typical case.
LONGEST_FAILURE_SUMMARY = 'The selected model returned invalid application documents.'


def _repair_chars(attempt, summary=LONGEST_FAILURE_SUMMARY, diagnostics=REPAIR_DIAGNOSTICS_BUDGET):
    """Size of the repair block on `attempt` -- 1 and 2 are the ones the loop actually appends."""
    return len(REPAIR_BLOCK.format(attempt=attempt, summary=summary, diagnostics='x' * diagnostics))

# Measured on the owner's machine 2026-09-09, from LM Studio refusing a trivial one-file probe: the
# tokens codex spends on its own system prompt and tool definitions before a single byte of ours.
# Not computed here -- nothing in this repo builds it, codex does -- and paid once per CLI run,
# which means once per attempt.
CODEX_OVERHEAD_TOKENS = 9448
# The one calibration point available for the chars/token ratio, same session: LM Studio's own
# tokenizer counted 39,129 tokens for a request whose user prompt was 140,478 chars plus the 9,448
# above. Reported as a footnote rather than baked in as the default: one measurement from one
# tokenizer says which way the error points, it is not a calibration. --chars-per-token is the knob
# for the next measurement.
MEASURED_PROMPT_CHARS = 140478
MEASURED_REQUEST_TOKENS = 39129


def _console_safe(text):
    """Company and title strings come from job postings: umlauts and emoji both turn up, and a
    cp1252 Windows console crashes on them (backfill_interview_dates.py carries the same guard)."""
    encoding = getattr(sys.stdout, 'encoding', '') or 'utf-8'
    return text.encode(encoding, 'replace').decode(encoding, 'replace')


def _resolve_user(value):
    users = get_user_model().objects
    found = users.filter(pk=value).first() if value.isdigit() else None
    return found or users.filter(email__iexact=value).first() or users.filter(username__iexact=value).first()


class Command(BaseCommand):
    help = ('TASK-224: break a CV generation request down by component without sending it anywhere. '
            'Prints characters and an ESTIMATED token count per part of the prompt, the parts that '
            'arrive through the model file-reading tool calls instead of in the prompt body, and what '
            'a failed generation costs across all three attempts. Read-only: no provider is launched, '
            'nothing is written, and no evidence, CV or profile text is printed -- sizes only.')

    def add_arguments(self, parser):
        parser.add_argument('--user', default='', help='Account email, username or id. Defaults to CODEX_CV_OWNER_EMAIL.')
        parser.add_argument('--job', type=int, default=0, help="Job id. Defaults to the account's newest job with usable source text.")
        parser.add_argument('--letter', action='store_true', help='Measure a CV+letter generation. Default is CV only.')
        parser.add_argument('--chars-per-token', type=float, default=4.0,
                            help='Chars per token for the estimate (default 4.0). A knob, not a fact -- see the footnote.')

    def handle(self, *args, **opts):
        ratio = opts['chars_per_token']
        if ratio <= 0:
            raise CommandError('--chars-per-token must be greater than zero.')

        user = _resolve_user(opts['user'] or (settings.CODEX_CV_OWNER_EMAIL or '').strip())
        if not user:
            raise CommandError('No such account. Pass --user with an email, username or id (CODEX_CV_OWNER_EMAIL did not resolve).')
        # filter().first(), not user_profile_settings(): that one is a get_or_create, and a report
        # must not create a row on the owner's database.
        profile = UserProfile.objects.filter(user=user).first()
        if not profile:
            raise CommandError(f'{user} has no profile row, so there is no prompt to measure.')

        if opts['job']:
            job = accessible_jobs(user).filter(id=opts['job']).first()
            if not job:
                raise CommandError(f'Job {opts["job"]} is not readable by {user}.')
        else:
            # source_text is a property over two columns, so "has usable text" cannot be a filter.
            # Newest 50 is far enough back to find one and bounded enough not to walk the table.
            job = next((row for row in accessible_jobs(user).order_by('-id')[:50] if row.is_meaningful_source(row.source_text)), None)
            if not job:
                raise CommandError(f"None of {user}'s 50 newest jobs has usable source text. Pass --job.")
        if not job.is_meaningful_source(job.source_text):
            raise CommandError(f'Job {job.id} has no usable source text; generate_cv_package would refuse it too.')

        templates = user_templates(user)
        if not templates:
            raise CommandError(f'{user} has no CV template stored. Add one with manage.py import_cv_assets.')
        # Same preselection the Generate panel makes (cv_generator.generation_preview), minus its
        # available_model_options() call, which shells out to codex and probes ollama.
        language = detect_job_language(job)
        cv_key = language if language in templates else next(iter(templates))
        cv_asset = templates[cv_key]['cv']
        letter_key = next(iter(templates[cv_key]['letters']), '')
        letter_asset = templates[cv_key]['letters'].get(letter_key)
        create_letter = bool(opts['letter'] and letter_asset)
        if opts['letter'] and not letter_asset:
            self.stdout.write(self.style.WARNING(f'No letter template under the {cv_key} CV; measuring the CV-only prompt.'))

        # The exact call views.generate_cv_documents makes, with the workspace blanked so that the
        # evidence snapshot it would otherwise refresh is not written by a read-only report.
        workspace = settings.CODEX_CV_WORKSPACE
        settings.CODEX_CV_WORKSPACE = ''
        try:
            context = load_candidate_evidence(build_candidate_profile_text(user),
                                              profile.learned_application_preferences, profile.candidate_evidence)
        except RuntimeError as exc:
            raise CommandError(str(exc)) from None
        finally:
            settings.CODEX_CV_WORKSPACE = workspace

        cv_name, letter_name = _target_names(job, applicant_name(user))
        prompt = _prompt(job, context, cv_name, letter_name, cv_key, letter_key, create_letter=create_letter)

        # Each part measured at its own source, never by splitting the assembled prompt back up on
        # its section headers: evidence text that happened to contain a header string would
        # mis-split it silently.
        stored = (profile.candidate_evidence or '').strip()
        evidence = _compact_candidate_evidence(stored) if stored else _compact_candidate_evidence(
            Path(settings.CODEX_CANDIDATE_EVIDENCE_PATH).read_text(encoding='utf-8').strip())
        rules = Path(settings.CODEX_APPLICATION_RULES_PATH).read_text(encoding='utf-8').strip()
        parts = [
            ('learned application preferences', len(profile.learned_application_preferences.strip())),
            ('candidate evidence (after compaction)', len(evidence)),
            ('DACHApply profile notes', len(build_candidate_profile_text(user))),
            ('mandatory application adaptation rules', len(rules)),
            ('job description (the only per-job part)', len(job.source_text or '')),
        ]
        # Whatever the named parts do not account for: _prompt's own rules and headers plus the
        # existing evaluation JSON. Derived rather than separately measured, so the column always
        # adds up -- and if a named part ever stops being measured correctly, this is where it shows.
        residual = len(prompt) - sum(size for _, size in parts)
        parts.append(('prompt scaffolding, headers, evaluation JSON', residual))

        def tokens(chars):
            return round(chars / ratio)

        def row(label, chars, share_of=0, note=''):
            share = f'{100 * chars / share_of:5.1f}%' if share_of else ''
            self.stdout.write(_console_safe(f'  {label:<44}{chars:>10,}{tokens(chars):>10,}{share:>8}  {note}'.rstrip()))

        target = 'CV and motivation letter' if create_letter else 'CV only'
        self.stdout.write(_console_safe(f'CV prompt size for {user} -- job {job.id} ({job.company} - {job.title}), {target}'))
        self.stdout.write(_console_safe(f'CV template: {cv_asset.filename}' + (f' / letter: {letter_asset.filename}' if create_letter else '')))
        self.stdout.write('Nothing was sent to a provider: the prompt was built and measured, not run.')

        self.stdout.write(f'\n{"USER PROMPT, one attempt":<46}{"chars":>10}{"~tokens":>10}{"share":>8}')
        for label, size in parts:
            row(label, size, len(prompt))
        row('TOTAL', len(prompt), len(prompt))
        if residual < 0:
            self.stdout.write(self.style.ERROR(
                'The named parts add up to MORE than the prompt, so one of them is being double-counted and this '
                'breakdown is stale. Re-check load_candidate_evidence and _prompt before believing the table.'))

        self.stdout.write('\nREAD THROUGH TOOL CALLS -- not in the prompt above, paid all the same')
        self.stdout.write('  The model reads these files itself, and every byte it reads is sent back with the next')
        self.stdout.write('  request. Nothing in the prompt shows their size, which is why they had to be measured')
        self.stdout.write('  rather than argued about.')
        self.stdout.write(f'  {"codex system prompt + tool definitions":<44}{"--":>10}{CODEX_OVERHEAD_TOKENS:>10,}          measured, not estimated')
        row('CV template', len(cv_asset.source or ''), note=cv_asset.filename)
        if create_letter:
            row('letter template', len(letter_asset.source or ''), note=letter_asset.filename)

        # Attempt 1 sends the prompt alone; attempts 2 and 3 each append their own repair block.
        repairs = [_repair_chars(attempt) for attempt in range(1, GENERATION_ATTEMPTS)]
        prompt_chars = GENERATION_ATTEMPTS * len(prompt) + sum(repairs)
        template_chars = GENERATION_ATTEMPTS * (len(cv_asset.source or '') + (len(letter_asset.source or '') if create_letter else 0))
        overhead = GENERATION_ATTEMPTS * CODEX_OVERHEAD_TOKENS
        self.stdout.write(f'\nONE FAILED GENERATION -- {GENERATION_ATTEMPTS} attempts, all failing')
        row('attempt 1: the prompt above', len(prompt))
        for attempt, repair in enumerate(repairs, start=1):
            row(f'attempt {attempt + 1}: the prompt + a repair block', len(prompt) + repair)
        row('prompt subtotal', prompt_chars)
        self.stdout.write(f'  {f"+ codex system prompt & tools, {GENERATION_ATTEMPTS} x {CODEX_OVERHEAD_TOKENS:,}":<44}{"--":>10}{overhead:>10,}')
        row(f'+ template reads, {GENERATION_ATTEMPTS} x each file', template_chars)
        self.stdout.write(f'  {"TOTAL for a generation that produces nothing":<44}{prompt_chars + template_chars:>10,}'
                          f'{tokens(prompt_chars + template_chars) + overhead:>10,}')
        self.stdout.write(f'  Each repair block is at most {repairs[0]:,} chars: {_repair_chars(1, summary="", diagnostics=0):,} of fixed instructions, '
                          f'{len(LONGEST_FAILURE_SUMMARY)} of failure summary, and the last')
        self.stdout.write(f'  {REPAIR_DIAGNOSTICS_BUDGET:,} chars of diagnostics. Attempt 1 carries none, attempts 2 and 3 carry one each, so the')
        self.stdout.write('  prompt GROWS on retry. Every attempt is a separate CLI run, so codex\'s system prompt is paid again')
        self.stdout.write('  each time, and the repair prompt tells the model to read the copied TeX files again -- counted')
        self.stdout.write('  here as re-read on every attempt, which is the ceiling; a model that skips the read pays less.')

        measured_ratio = MEASURED_PROMPT_CHARS / (MEASURED_REQUEST_TOKENS - CODEX_OVERHEAD_TOKENS)
        self.stdout.write(f'\nToken counts are ESTIMATES: chars / {ratio:g}. No tokenizer is installed (none in pyproject.toml)')
        self.stdout.write('and adding a dependency for a report is not worth it, so this is arithmetic, not a count.')
        self.stdout.write(f"The one real measurement available -- LM Studio's own tokenizer, 2026-09-09 -- read")
        self.stdout.write(f'{MEASURED_REQUEST_TOKENS:,} tokens for a request of {MEASURED_PROMPT_CHARS:,} prompt chars plus {CODEX_OVERHEAD_TOKENS:,} tokens of codex')
        self.stdout.write(f'overhead: about {measured_ratio:.1f} chars per token on that text, so chars/4 read roughly '
                          f'{100 * (measured_ratio / 4 - 1):.0f}% high there.')
        self.stdout.write('Pass --chars-per-token to try another ratio; nothing else in the report changes.')
