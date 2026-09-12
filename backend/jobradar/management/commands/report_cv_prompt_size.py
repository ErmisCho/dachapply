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

TASK-225 adds --learned, which breaks the largest of those rows -- the learned application
preferences -- down by entry, scope, duplication and what a recency cap would cost. It measures the
field so a bound can be argued from its real shape; it does not bound anything, and nothing under
that flag changes what generation sends either.
"""
import re
import sys
from difflib import SequenceMatcher
from math import ceil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from jobradar.models import UserProfile
from jobradar.services.access import accessible_jobs
from jobradar.services.cv_generator import (LEARNED_ENTRY as cv_generator_LEARNED_ENTRY,
                                            _compact_candidate_evidence, _prompt, _target_names,
                                            applicant_name, bound_learned_preferences,
                                            detect_job_language, load_candidate_evidence,
                                            preference_entries, user_templates)
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


# TASK-225. The learned-preference field is one line per CV readjustment, written by
# cv_tasks._learn_application_preference as `- [{scope}] {instructions}`, deduplicated by exact
# casefold match on the whole line and never pruned. The profile UI edits that same field as free
# text, so lines the writer could not have produced are expected rather than exceptional: they are
# counted as unscoped, never dropped, and nothing below may raise on one.
LEARNED_SCOPES = ('CV', 'Letter', 'CV + letter')
# Case-sensitive on purpose: the writer only ever emits those three, so a differently-cased scope is
# a hand edit, and the report's job is to say so rather than to tidy it away.
# Imported, not redefined: cv_generator.preference_exclusion parses the same shape to decide
# what reaches the prompt, and two regexes for one stored format is how they drift apart.
LEARNED_ENTRY = cv_generator_LEARNED_ENTRY
LEARNED_NOISE = re.compile(r'[^\w\s]+')  # so that "four lines." and "four lines" normalise the same
# ponytail: the near-duplicate pass is O(n^2) and runs over the NEWEST entries only. 400 is ~80k
# difflib comparisons of short strings, well under a second; the whole field would be several times
# that for a number whose only job is to say whether a fuzzy rule is worth writing. Raise the
# ceiling if the answer turns out to be close -- the compared count is printed, so it cannot hide.
NEAR_DUP_CEILING = 400
NEAR_DUP_RATIO = .9  # conservative, so the count reads as a floor for "how much of this repeats"
LEARNED_CAPS = (10, 25, 50, 100, 200, 400)


def _learned_entries(blob):
    """[(scope, line)] for every non-blank line; scope is '' for a line the writer did not produce."""
    entries = []
    for line in (blob or '').splitlines():
        line = line.strip()
        if not line:
            continue
        match = LEARNED_ENTRY.match(line)
        scope = match.group(1) if match else ''
        entries.append((scope if scope in LEARNED_SCOPES else '', line))
    return entries


def _learned_key(line):
    """The entry as a more forgiving dedup would see it: scope prefix gone, punctuation gone, no
    case, whitespace collapsed. The prefix is stripped whenever it parses at all, even when the
    scope is not one of the three, so that a hand-edited prefix cannot make a repeat look unique."""
    match = LEARNED_ENTRY.match(line)
    return ' '.join(LEARNED_NOISE.sub(' ', (match.group(2) if match else line).casefold()).split())


def _blob_chars(lines):
    """What the field would hold if it held exactly these lines. The joining newlines count: at ~900
    entries they are ~900 chars of the prompt, and a cap table that ignored them would be wrong."""
    return len('\n'.join(lines))


def _pctile(sorted_lengths, fraction):
    """Nearest-rank, not statistics.quantiles: that one interpolates, and half of one entry's length
    is not a length any entry has."""
    return sorted_lengths[max(0, min(len(sorted_lengths) - 1, ceil(fraction * len(sorted_lengths)) - 1))]


def _near_duplicate_pairs(keys, ceiling=NEAR_DUP_CEILING, ratio=NEAR_DUP_RATIO):
    """(entries with an earlier near-twin, entries compared), over the last `ceiling` keys.

    Counts entries and not pairs, so the number reads directly as "this many could go". difflib is
    stdlib: no similarity dependency is added for a report.
    """
    recent = keys[-ceiling:]
    matcher = SequenceMatcher(autojunk=False)
    matched = 0
    for index, key in enumerate(recent):
        matcher.set_seq2(key)
        for earlier in recent[:index]:
            matcher.set_seq1(earlier)
            # real_quick_ratio and quick_ratio are cheap upper bounds on ratio; the real comparison
            # only runs when both of them leave the threshold reachable.
            if matcher.real_quick_ratio() >= ratio and matcher.quick_ratio() >= ratio and matcher.ratio() >= ratio:
                matched += 1
                break
    return matched, len(recent)


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
        # Behind a flag, not always on: the TASK-225 breakdown is four tables, about as long again as
        # the whole default report, and it answers a different question (how should this field be
        # bounded) than the default one (what is the request made of). The default stays one screen.
        parser.add_argument('--learned', action='store_true',
                            help='TASK-225: break the learned application preferences down -- entry count, length '
                                 'distribution, scope split, duplication the current dedup missed, and what a '
                                 'recency cap would cost. Measures the field; changes nothing.')

    def _report_learned_preferences(self, blob, prompt_chars, bounded_chars, row, tokens):
        """TASK-225: characterise the field, so its bound is chosen from measured shape rather than
        from whichever rule is easiest to write.

        Counts, lengths and positions only. No entry text is printed, not truncated and not sampled,
        so duplicates are identified by count and the cap table by position -- the same AC7 rule the
        rest of the report follows, and the reason none of this needs _console_safe: every value
        below is a number, so no preference-derived string reaches a cp1252 console at all.
        """
        entries = _learned_entries(blob)
        self.stdout.write('\nLEARNED APPLICATION PREFERENCES -- the largest row above, broken down')
        if not entries:
            self.stdout.write('  The field is empty: there is nothing to bound.')
            return
        lines = [line for _, line in entries]
        lengths = sorted(len(line) for line in lines)
        total = _blob_chars(lines)
        # Every share below is against the prompt as it would be with NOTHING dropped, so the
        # numbers stay comparable to the pre-bound ones and to each other. `prompt_chars` is the
        # bounded prompt -- dividing by that would make a cap's share rise as the cap tightened, and
        # go negative once the stored field exceeded the whole prompt. It did, at -375.6%.
        unbounded_prompt = prompt_chars - bounded_chars + total

        def as_sent(size):
            """The prompt this many chars of preferences would produce, for the share denominator."""
            return unbounded_prompt - total + size

        # 34 + 10 puts the chars column exactly where row()'s lands, so these tables line up with the
        # component table above without sharing a formatter with it.
        def count_row(label, kept, size, share_of=None):
            share_of = unbounded_prompt if share_of is None else share_of
            share = f'{100 * size / share_of:5.1f}%' if share_of else ''
            self.stdout.write(f'  {label:<34}{kept:>10,}{size:>10,}{tokens(size):>10,}{share:>8}')

        def header(title):
            self.stdout.write(f'\n  {title}')
            self.stdout.write(f'  {"":<34}{"entries":>10}{"chars":>10}{"~tokens":>10}{"share":>8}')

        self.stdout.write(f'  {len(entries):,} entries, {total:,} chars, {100 * total / unbounded_prompt:.1f}% of the prompt if every one were sent: one line per CV')
        self.stdout.write('  readjustment, appended by cv_tasks._learn_application_preference and never removed.')
        self.stdout.write('  The entries carry NO timestamp -- the field is a plain TextField that is appended to -- so')
        self.stdout.write('  nothing in this section measures AGE. "Last K" below means position in the field, and the')
        self.stdout.write('  profile UI edits that field as free text, so even the order is an assumption, not a guarantee.')

        self.stdout.write('\n  ENTRY LENGTH (per-entry lengths exclude the newline that joins them; the total includes it)')
        row('shortest entry', lengths[0])
        row('median entry', _pctile(lengths, .5))
        row('p90 entry', _pctile(lengths, .9))
        row('longest entry', lengths[-1])
        row(f'all {len(entries):,} entries', total, unbounded_prompt)

        header('SCOPE -- the prefix cv_tasks writes; anything else is a hand edit through the profile UI')
        for scope in LEARNED_SCOPES:
            picked = [line for entry_scope, line in entries if entry_scope == scope]
            count_row(f'- [{scope}]', len(picked), _blob_chars(picked))
        unscoped = [line for scope, line in entries if not scope]
        count_row('unscoped (hand-edited)', len(unscoped), _blob_chars(unscoped))

        header('DUPLICATION -- what exact-casefold dedup, the rule in cv_tasks, let through')
        # Newest wins: the prompt itself says "newer entries override older ones", so the survivor of
        # a repeated instruction is the LAST copy and the first is the one a forgiving dedup drops.
        seen, survivors = set(), []
        for line in reversed(lines):
            key = _learned_key(line)
            if key not in seen:
                seen.add(key)
                survivors.append(line)
        survivors.reverse()
        count_row('after casefold+punctuation+space', len(survivors), _blob_chars(survivors))
        count_row('removed by that alone', len(lines) - len(survivors), total - _blob_chars(survivors))

        matched, compared = _near_duplicate_pairs([_learned_key(line) for line in survivors])
        self.stdout.write(f'  Further: {matched:,} of the newest {compared:,} survivors are at least {NEAR_DUP_RATIO:.0%} similar '
                          f'(difflib) to an earlier')
        self.stdout.write(f'  survivor, so a fuzzy rule would remove that many again. Compared pairwise up to {NEAR_DUP_CEILING} entries')
        self.stdout.write('  and identified by count only: no pair is quoted, these are the owner\'s career instructions.')

        header('A RECENCY CAP -- keeping only the last K entries')
        for cap in LEARNED_CAPS:
            if cap >= len(lines):
                break  # a cap that keeps everything is the "all" row below, and is printed once
            kept = lines[-cap:]
            size = _blob_chars(kept)
            # Share of the SHRUNKEN prompt: the chars a cap removes leave the denominator too, so
            # this is what the request would then look like, not today's share scaled down.
            count_row(f'last {cap:,}', len(kept), size, as_sent(size))
        count_row('all (no cap at all)', len(lines), total)
        # An entry cap is what this table shows because entry position is the only order the field
        # has. It is NOT what ships: entries span 67-4,979 chars here, so last-K buys an unknown
        # number of chars. The live rule is a character budget, and this is the row that is real.
        budget = settings.CODEX_LEARNED_PREFERENCES_BUDGET
        # TASK-236: the live rule is preference_entries THEN the budget, so this composes both --
        # the same composition load_candidate_evidence makes. Measuring the raw field here printed
        # the pre-change answer under a label reading IN FORCE, and the main table above, which does
        # compose them, would then contradict this row inside a single run of the same report.
        bounded, kept_entries, _ = bound_learned_preferences(preference_entries(blob), budget)
        # No digits in the label: the row parser reads the first number on the line as the entry
        # count, so a budget printed inside the label would be swallowed as one.
        label = 'IN FORCE: the character budget' if budget > 0 else 'IN FORCE: unbounded'
        count_row(label, kept_entries, len(bounded), as_sent(len(bounded)))

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
        # TASK-225 (AC2): what the prompt CARRIES, not what the field stores. The bound lives in
        # cv_generator.bound_learned_preferences and _prompt was built through it above, so calling
        # the same helper here is what stops the report and generation from ever disagreeing --
        # measuring the raw field instead would push the whole difference into `residual` unseen.
        # TASK-236 put preference_entries in front of the bound in load_candidate_evidence, so the
        # composition -- not just the bound -- is what the prompt carries. Composing only one of the
        # two here is the exact failure the paragraph above describes, and it would be invisible:
        # the excluded chars would land in `residual` and the report would still add up.
        eligible = preference_entries(profile.learned_application_preferences)
        bounded, kept_entries, total_entries = bound_learned_preferences(
            eligible, settings.CODEX_LEARNED_PREFERENCES_BUDGET)
        stored_learned = len(profile.learned_application_preferences.strip())
        stored_entries = len([l for l in profile.learned_application_preferences.splitlines() if l.strip()])
        excluded_entries = stored_entries - total_entries
        excluded_chars = stored_learned - len(eligible.strip())
        parts = [
            ('learned application preferences', len(bounded)),
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
        # The stored field keeps growing whatever the bound does -- it is append-only and untouched
        # by design (AC3), so the owner can still read and edit every entry in account settings.
        # What this line reports is the gap between what is KEPT and what is SENT, which is the only
        # number the bound can move and the one AC6 re-reads to check the bound still holds.
        if excluded_entries:
            self.stdout.write(f'  {excluded_entries:,} of {stored_entries:,} stored entries are not durable preferences '
                              f'(CODEX_PREFERENCE_MAX_CHARS, CODEX_PREFERENCE_SKIP_TRUNCATED):')
            self.stdout.write(f'  {excluded_chars:,} chars of pasted brief were dropped BEFORE the budget was spent, so the '
                              f'{total_entries:,} real preferences compete for it instead. Run review_learned_preferences to see each one.')
        if settings.CODEX_LEARNED_PREFERENCES_BUDGET > 0 and kept_entries < total_entries:
            self.stdout.write(f'  Learned preferences are bounded at {settings.CODEX_LEARNED_PREFERENCES_BUDGET:,} chars '
                              f'(CODEX_LEARNED_PREFERENCES_BUDGET): the newest {kept_entries:,} of')
            self.stdout.write(f'  {total_entries:,} entries reached the prompt. The field still stores all {stored_learned:,} chars '
                              f'-- nothing was deleted,')
            self.stdout.write(f'  and {stored_learned - len(bounded):,} chars of it are simply not sent. Run --learned to see how the rest breaks down.')
        elif settings.CODEX_LEARNED_PREFERENCES_BUDGET <= 0:
            self.stdout.write('  Learned preferences are UNBOUNDED (CODEX_LEARNED_PREFERENCES_BUDGET <= 0): every stored entry is sent.')
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

        if opts['learned']:
            self._report_learned_preferences(profile.learned_application_preferences, len(prompt), len(bounded), row, tokens)

        measured_ratio = MEASURED_PROMPT_CHARS / (MEASURED_REQUEST_TOKENS - CODEX_OVERHEAD_TOKENS)
        self.stdout.write(f'\nToken counts are ESTIMATES: chars / {ratio:g}. No tokenizer is installed (none in pyproject.toml)')
        self.stdout.write('and adding a dependency for a report is not worth it, so this is arithmetic, not a count.')
        self.stdout.write(f"The one real measurement available -- LM Studio's own tokenizer, 2026-09-09 -- read")
        self.stdout.write(f'{MEASURED_REQUEST_TOKENS:,} tokens for a request of {MEASURED_PROMPT_CHARS:,} prompt chars plus {CODEX_OVERHEAD_TOKENS:,} tokens of codex')
        self.stdout.write(f'overhead: about {measured_ratio:.1f} chars per token on that text, so chars/4 read roughly '
                          f'{100 * (measured_ratio / 4 - 1):.0f}% high there.')
        self.stdout.write('Pass --chars-per-token to try another ratio; nothing else in the report changes.')
