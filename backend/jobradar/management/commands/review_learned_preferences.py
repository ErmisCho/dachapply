"""TASK-229 AC3/AC5: the review list for the learned-preference field, for a human to work through.

TASK-225 measured the field first: one line per CV readjustment, entries spanning 67-4,979 chars
(median 1,521). Those are not one-line preferences, they are whole pasted readjustment briefs.
TASK-229 AC1 then measured what is inside them: of 713 distinctive terms, 381 (53%) appear nowhere in
the authoritative candidate evidence, and 322 of those sit only in entries the 16,000-char bound
drops. So claims about what the owner did in a past role are living in an append-only style log.

This command does not fix that and does not try to classify it away. AC3 allows two answers, and this
is the second one: on this data a fact-asserting entry CANNOT be told apart from a style-asserting one
automatically, because at that median an ENTRY is not the unit a label fits -- a pasted brief can ask
for a shorter summary and assert a past role in the same breath, and no per-entry verdict is honest
about that. How often it actually happens is the count this report PRINTS ("both kinds of signal"),
measured on the field in front of it rather than asserted here: nobody has labelled these entries by
hand, so the rule below has never been scored, and the report says so where the owner reads it.
What can be done mechanically is to show the owner the SIGNALS -- which writing verbs an entry
contains, which of its distinctive terms have nothing behind them in the evidence, which dates and
measured quantities it carries -- and let them decide. Every label printed below is accompanied by the
signal that produced it, and the report states in its own header that the label has no measured
accuracy: it has never been checked against a labelled sample, because no labelled sample exists.

AC5 is the other half: pairs that are about the same thing but ask for opposite things. A repeat is
not a contradiction -- a report that flagged every near-duplicate would be worthless -- so a pair whose
normalised text is near-identical is excluded by the same difflib rule report_cv_prompt_size uses for
TASK-225, and a pair that names the same quantity for the same unit is read as agreement rather than
as conflict.

TASK-236 adds one column and no judgement: every entry is marked with whether it may reach the CV
prompt as a durable preference, by the SAME rule the prompt builder applies -- imported from
cv_generator, never a second copy, for the reason the parsing helpers above are imported too. That
mark is a mechanical fact about length and about the 5,000-char cap the readjustment box applies at
views.py:2043, not a verdict on the entry: an entry can be excluded from the prompt and still be the
truest and most important thing in the field. Nothing is dropped from this listing -- every entry the
field holds is still printed, excluded ones included, with the reason next to them, because TASK-229's
by-hand review of the claims in this field is still open and depends on seeing all of them.

Read-only, and more strictly than a report usually needs to be: no save(), no update(), no provider,
no migration, and the evidence is read without going through load_candidate_evidence, which would
refresh a compaction snapshot on the workspace. The stored field is byte-identical after a run --
TASK-225 deliberately never writes it, and test_review_learned_preferences asserts that byte for byte.

The owner's own entry text DOES reach their console: that is the point of a review list. Nothing
personal reaches this repository -- not this file, not its tests, not a help string. The repo is public.
"""
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jobradar.management.commands.report_cv_prompt_size import (LEARNED_ENTRY, NEAR_DUP_RATIO, _console_safe,
                                                                _learned_entries, _learned_key, _resolve_user)
from jobradar.models import UserProfile
from jobradar.services.cv_generator import (WIRE_INSTRUCTION_CAP, _compact_candidate_evidence,
                                            preference_exclusion)

# The same field report_cv_prompt_size --learned measures, parsed by the same imported helpers rather
# than by a second copy of the rules: two reports that disagreed about what an entry IS would be worse
# than either of them being wrong alone.

# STYLE signal. Instructions about how to WRITE something, in the imperative the readjustment box
# invites. Deliberately broad: a wrongly missing style hit turns an entry that is half style into a
# confident likely-FACT, and a confident wrong label is worse than "unclear" (AC3).
STYLE_TERMS = frozenset({
    'abbreviate', 'adjective', 'adjectives', 'avoid', 'bold', 'bullet', 'bulleted', 'bullets', 'capitalise',
    'capitalize', 'caption', 'concise', 'concisely', 'condense', 'elaborate', 'emphasis', 'emphasise',
    'emphasize', 'expand', 'font', 'format', 'formatting', 'grammar', 'headline', 'heading', 'highlight',
    'italic', 'jargon', 'layout', 'length', 'lengthen', 'line', 'lines', 'omit', 'paragraph', 'paragraphs',
    'phrase', 'phrasing', 'punctuation', 'rephrase', 'reorder', 'reword', 'rewrite', 'sentence', 'sentences',
    'shorten', 'shorter', 'spelling', 'style', 'tense', 'tone', 'translate', 'trim', 'verbose', 'voice',
    'wording', 'wordy', 'write', 'writing', 'written',
    # Verbs that are only about writing in this field's context, but are common enough to be worth
    # naming separately: they are why most entries end up carrying a style signal at all.
    'delete', 'drop', 'exclude', 'include', 'keep', 'mention', 'remove', 'reuse', 'use',
})
WORD = re.compile(r"[^\W\d_][\w'+#-]*")

# FACT signal. A capital mid-sentence, an acronym, a year, or a quantity with a unit that is not a
# unit of writing. None of these is proof of a claim -- AC1 said so in the note that reported 381 as
# an upper bound -- which is why the terms themselves are printed rather than just counted.
CAPITALISED = re.compile(r'(?<!\w)([A-Z][\w+#&/.-]*)')
SENTENCE_BOUNDARY = '.!?:;•("\'-–—'
YEAR = re.compile(r'\b(?:19|20)\d{2}\b')
NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
                'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}
QUANTITY = re.compile(r'\b(\d[\d.,]*|' + '|'.join(NUMBER_WORDS) + r')\b\s*(%|[A-Za-z]{2,15}\b)', re.I)
# "four lines" is a quantity about the document, not about the career: it counts for the contradiction
# pass (two entries demanding different summary lengths DO conflict) but never as a factual claim.
WRITING_UNITS = frozenset({'bullet', 'char', 'character', 'column', 'item', 'line', 'page', 'paragraph',
                           'point', 'section', 'sentence', 'word'})

# AC5. Two axes only, each one printed with the words that fired it, because every axis is a guess and
# the owner has to be able to see a bad one immediately.
OPPOSED_AXES = (
    ('length', frozenset({'shorten', 'shorter', 'short', 'condense', 'trim', 'concise', 'brief', 'tighten', 'cut'}),
     frozenset({'lengthen', 'longer', 'expand', 'extend', 'elaborate', 'fuller', 'detailed'})),
    ('inclusion', frozenset({'include', 'mention', 'keep', 'retain', 'list', 'show', 'state', 'always'}),
     frozenset({'remove', 'omit', 'drop', 'delete', 'exclude', 'avoid', 'never', 'without'})),
)
AXIS_WORDS = frozenset().union(*(side for _, positive, negative in OPPOSED_AXES for side in (positive, negative)))
STOPWORDS = frozenset({
    'and', 'are', 'any', 'all', 'about', 'after', 'also', 'always', 'been', 'being', 'both', 'but', 'can',
    'could', 'did', 'does', 'each', 'else', 'even', 'ever', 'every', 'for', 'from', 'had', 'has', 'have',
    'her', 'here', 'his', 'how', 'into', 'its', 'just', 'like', 'made', 'make', 'may', 'might', 'more',
    'most', 'much', 'must', 'need', 'not', 'now', 'off', 'one', 'only', 'onto', 'our', 'out', 'over',
    'own', 'per', 'put', 'same', 'she', 'should', 'since', 'some', 'such', 'than', 'that', 'the', 'their',
    'them', 'then', 'there', 'these', 'they', 'this', 'those', 'through', 'too', 'under', 'until', 'upon',
    'very', 'was', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with',
    'would', 'you', 'your',
})
# Containment, not Jaccard: entries here differ 74x in length (TASK-225 measured 67 to 4,979 chars), and
# Jaccard between a one-line preference and a 5,000-char brief is near zero even when the short one is
# entirely about a subtopic of the long one. min() answers "is the smaller one about the same thing".
TOPIC_OVERLAP = .5
MIN_TOPIC_WORDS = 2  # containment over a single shared word is noise, not a topic
# ponytail: the pair pass is O(n^2), matching _near_duplicate_pairs in report_cv_prompt_size, and the
# field holds 43 entries. 400 is ~80k difflib comparisons of short strings, well under a second. The
# compared count is printed, so a field that outgrows the ceiling cannot hide it.
PAIR_CEILING = 400

LABEL_STYLE, LABEL_FACT, LABEL_UNCLEAR = 'likely-STYLE', 'likely-FACT', 'unclear'
# TASK-236 --prompt, worded as the two sides of one mechanical question rather than as good/bad.
REACH_WORDS = {'reaching': 'reaching the prompt', 'excluded': 'excluded from the prompt'}


def _body(line):
    """The entry without the `- [CV]` prefix the writer adds: its scope is cv_tasks's word, not the
    owner's, and counting `CV` as one of their distinctive terms would be counting our own noise."""
    match = LEARNED_ENTRY.match(line)
    return (match.group(2) if match else line).strip()


def _stem(word):
    """Crude suffix folding, so that `expanded` reaches the same vocabulary entry as `expand`.

    Not a stemmer and not trying to be: it exists because the entries are written in free prose, and
    an axis that matched only the bare imperative would miss `the summary should be expanded` -- which
    is exactly the kind of contradiction AC5 is for. The 4-character floor keeps `using` from becoming
    `us`; the words it still mangles (`writing` -> `writ`) are spelled out in the vocabularies above.
    """
    for suffix in ('ing', 'ed', 'es', 's'):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[:-len(suffix)]
    return word


def _known(word, vocabulary):
    return word in vocabulary or _stem(word) in vocabulary


def _distinctive_terms(body):
    """Capitals that are not just grammar: mid-sentence capitalised words, plus acronyms anywhere.

    A capital after a full stop is the start of a sentence and says nothing. An ALL-CAPS token is kept
    wherever it sits, because acronyms are the most load-bearing fact signal in this field and most
    of them would otherwise be lost to sentence position.
    """
    terms = []
    for match in CAPITALISED.finditer(body):
        term = match.group(1).strip('.,-/')
        if len(term) < 2:
            continue
        before = body[:match.start()].rstrip()
        if term.isupper() or (before and before[-1] not in SENTENCE_BOUNDARY):
            terms.append(term)
    return list(dict.fromkeys(terms))


def _quantities(body):
    """[(value, unit)] for '12 TB', '20%' and 'four lines' alike -- the field mixes digits and words,
    so 'four' and '4' have to normalise to the same number or two entries could contradict unseen."""
    found = []
    for match in QUANTITY.finditer(body):
        raw, unit = match.group(1).strip('.,'), match.group(2).casefold()
        if unit in STOPWORDS or YEAR.fullmatch(raw):
            continue  # '2019 was' is a date with a verb after it, and _analyse reports it as a date
        value = NUMBER_WORDS.get(raw.casefold())
        found.append((str(value) if value else raw.replace(',', '').rstrip('.'),
                      unit if unit == '%' else unit.rstrip('s')))
    return found


def _topic_words(words):
    """{stem: the word as written} for what the entry is ABOUT, with the vocabulary of ASKING stripped
    out: style verbs and the contradiction axes are how two entries differ, so leaving them in would
    make opposites look alike. Matched on the stem so `summaries` and `summary` are one subject; the
    surface form is carried along because `clos` is not a word to hand back to the owner."""
    topic = {}
    for word in words:
        if (len(word) > 2 and not _known(word, STOPWORDS) and not _known(word, STYLE_TERMS)
                and not _known(word, AXIS_WORDS) and word not in NUMBER_WORDS):
            topic.setdefault(_stem(word), word)
    return topic


def _corroborated(term, tokens):
    """True when every word-ish part of the term appears somewhere in the evidence. Part-wise so that
    'Node.js' or a hyphenated name is not reported absent merely because the evidence spaces it."""
    parts = [part for part in re.split(r'[^\w+#]+', term.casefold()) if part]
    return bool(parts) and all(part in tokens for part in parts)


def _analyse(index, scope, line, evidence_tokens):
    """Everything the report knows about one entry. Signals first, label last: the label is derived
    from them and never from anything the owner cannot see printed underneath it."""
    body = _body(line)
    words = [word.casefold() for word in WORD.findall(body)]
    style = Counter(word for word in words if _known(word, STYLE_TERMS))
    absent = [term for term in _distinctive_terms(body) if not _corroborated(term, evidence_tokens)]
    years = list(dict.fromkeys(YEAR.findall(body)))
    quantities = _quantities(body)
    facts = [quantity for quantity in quantities if quantity[1] not in WRITING_UNITS]
    by_unit = {}
    for value, unit in quantities:
        by_unit.setdefault(unit, set()).add(value)
    topic = _topic_words(words)
    axes = {name: ({word for word in words if _known(word, positive)},
                   {word for word in words if _known(word, negative)})
            for name, positive, negative in OPPOSED_AXES}
    if absent or years or facts:
        label = LABEL_UNCLEAR if style else LABEL_FACT
    else:
        label = LABEL_STYLE if style else LABEL_UNCLEAR
    return {'index': index, 'scope': scope, 'line': line, 'label': label, 'style': style,
            # TASK-236: the prompt builder's own rule, asked here rather than re-derived.
            'exclusion': preference_exclusion(line),
            'absent': absent, 'years': years, 'fact_quantities': facts, 'by_unit': by_unit,
            'topic': set(topic), 'subjects': topic, 'key': _learned_key(line), 'axes': axes,
            'both': bool(style) and bool(absent or years or facts)}


def _chars(entries):
    return sum(len(entry['line']) for entry in entries)


def _style_signal(entry):
    if not entry['style']:
        return 'none'
    return ', '.join(f'{word} x{count}' if count > 1 else word
                     for word, count in entry['style'].most_common(8))


def _fact_signal(entry):
    parts = []
    if entry['absent']:
        shown = ', '.join(entry['absent'][:8])
        extra = f' (+{len(entry["absent"]) - 8} more)' if len(entry['absent']) > 8 else ''
        parts.append(f'{len(entry["absent"])} term(s) absent from the evidence: {shown}{extra}')
    if entry['years']:
        parts.append(f'{len(entry["years"])} date(s): ' + ', '.join(entry['years']))
    if entry['fact_quantities']:
        parts.append(f'{len(entry["fact_quantities"])} measured quantity(ies): '
                     + ', '.join(f'{value} {unit}' for value, unit in entry['fact_quantities']))
    return ' | '.join(parts) if parts else 'none'


def _quantity_reasons(first, second):
    """(conflicting, agreeing) over the units both entries mention. Agreement is as load-bearing as
    conflict here: two entries that name the same size for the same thing are saying the same thing,
    whatever verbs they used to say it, and must not be reported as a contradiction (AC5)."""
    conflicting, agreeing = [], []
    for unit in sorted(set(first['by_unit']) & set(second['by_unit'])):
        mine, theirs = first['by_unit'][unit], second['by_unit'][unit]
        if mine != theirs:
            conflicting.append(f'{"/".join(sorted(mine))} {unit} vs {"/".join(sorted(theirs))} {unit}')
        else:
            agreeing.append(f'{"/".join(sorted(mine))} {unit}')
    return conflicting, agreeing


def _opposition(first, second):
    """Why these two look like they disagree, in words the owner can check -- or [] for "they don't"."""
    conflicting, agreeing = _quantity_reasons(first, second)
    reasons = [f'the same thing is given two different sizes: {reason}' for reason in conflicting]
    if conflicting or not agreeing:
        for name, _, _ in OPPOSED_AXES:
            first_positive, first_negative = first['axes'][name]
            second_positive, second_negative = second['axes'][name]
            if (first_positive and second_negative) or (first_negative and second_positive):
                reasons.append(f'opposed on {name}: #{first["index"]} says '
                               f'{", ".join(sorted(first_positive | first_negative))}, #{second["index"]} says '
                               f'{", ".join(sorted(second_positive | second_negative))}')
    return reasons


def _conflict_pairs(analysed, ceiling=PAIR_CEILING):
    """([(first, second, reasons, shared topic)], near-duplicates skipped, entries compared)."""
    considered = analysed[-ceiling:]
    matcher = SequenceMatcher(autojunk=False)
    pairs, duplicates = [], 0
    for position, entry in enumerate(considered):
        matcher.set_seq2(entry['key'])
        for earlier in considered[:position]:
            shared = entry['topic'] & earlier['topic']
            smaller = min(len(entry['topic']), len(earlier['topic']))
            if smaller < MIN_TOPIC_WORDS or len(shared) / smaller < TOPIC_OVERLAP:
                continue  # not about the same thing, so they cannot disagree about it
            matcher.set_seq1(earlier['key'])
            # real_quick_ratio and quick_ratio are cheap upper bounds; the real comparison only runs
            # when both leave the threshold reachable (the same order _near_duplicate_pairs uses).
            if (matcher.real_quick_ratio() >= NEAR_DUP_RATIO and matcher.quick_ratio() >= NEAR_DUP_RATIO
                    and matcher.ratio() >= NEAR_DUP_RATIO):
                duplicates += 1
                continue  # a repeat, not a conflict: report_cv_prompt_size --learned counts these already
            reasons = _opposition(earlier, entry)
            if reasons:
                pairs.append((earlier, entry, reasons, sorted(shared)))
    return pairs, duplicates, len(considered)


def _evidence(profile):
    """(compacted evidence, where it came from), by load_candidate_evidence's own precedence.

    Mirrored rather than called: that function writes a compaction snapshot into the CV workspace, and
    a review tool has no business writing anything. The precedence matters more than it looks --
    TASK-229 AC1's first attempt compared against UserProfile.candidate_evidence, which is EMPTY on
    the account this exists for, and reported 100% of terms uncorroborated. That was an artifact.
    """
    stored = (profile.candidate_evidence or '').strip()
    if stored:
        return _compact_candidate_evidence(stored), f'the stored UserProfile.candidate_evidence ({len(stored):,} chars)'
    path = settings.CODEX_CANDIDATE_EVIDENCE_PATH
    try:
        content = Path(path).read_text(encoding='utf-8').strip() if path else ''
    except OSError:
        content = ''
    if not content:
        raise CommandError('No candidate evidence to compare against: UserProfile.candidate_evidence is empty and the '
                           'file at CODEX_CANDIDATE_EVIDENCE_PATH is missing, unreadable or empty.')
    return _compact_candidate_evidence(content), f'the file at CODEX_CANDIDATE_EVIDENCE_PATH ({path})'


class Command(BaseCommand):
    help = ('TASK-229: list the learned application preferences with the signal that suggests each one asserts a '
            'FACT rather than a style preference, and the pairs that look like they contradict rather than repeat '
            'each other. A review list for a human, not a classifier: the label carries no measured accuracy and '
            'the report says so. Read-only -- nothing is written, no provider runs, and the stored field is left '
            "byte-identical. The entries themselves are printed, so this is for the owner's own console.")

    def add_arguments(self, parser):
        parser.add_argument('--user', default='', help='Account email, username or id. Defaults to CODEX_CV_OWNER_EMAIL.')
        parser.add_argument('--limit', type=int, default=10, help='How many entries to print (default 10, 0 for all).')
        parser.add_argument('--start', type=int, default=1,
                            help='First entry to print (default 1), so a long field is reviewed in sittings rather than in one wall of text.')
        parser.add_argument('--label', choices=('all', 'fact', 'style', 'unclear'), default='all',
                            help='Print only entries carrying this label. The counts underneath always cover the whole field.')
        parser.add_argument('--prompt', choices=('all', 'reaching', 'excluded'), default='all',
                            help='Print only the entries that may reach the CV prompt as durable preferences, or only '
                                 'the ones excluded from it (TASK-236). The counts underneath always cover the whole field.')
        parser.add_argument('--chars', type=int, default=300,
                            help='Characters of each entry to print (default 300, 0 for the whole entry).')

    def _excerpt(self, line, chars):
        return line if chars <= 0 or len(line) <= chars else f'{line[:chars]} ... (+{len(line) - chars:,} chars)'

    def _print_entry(self, entry, chars):
        scope = f'[{entry["scope"]}]' if entry['scope'] else '[hand-edited]'
        mark = '  EXCLUDED from the prompt' if entry['exclusion'] else ''
        self.stdout.write(_console_safe(f'\n#{entry["index"]}  {entry["label"]:<12}  {scope:<15}{len(entry["line"]):>7,} chars{mark}'))
        self.stdout.write(_console_safe(f'    style signal: {_style_signal(entry)}'))
        self.stdout.write(_console_safe(f'    fact signal : {_fact_signal(entry)}'))
        if entry['exclusion']:
            # The reason, and then what the reason is NOT: it is about the shape of the text, and the
            # entry is still stored and still printed below it whatever it says.
            self.stdout.write(_console_safe(f'    excluded    : {entry["exclusion"]} (a fact about length, not about whether the entry is true)'))
        self.stdout.write(_console_safe(f'    text        : {self._excerpt(entry["line"], chars)}'))

    def _print_reach(self, analysed):
        """TASK-236 AC5: what the prompt is given and what it is not, with the excluded half still
        listed above rather than quietly gone."""
        reaching = [entry for entry in analysed if not entry['exclusion']]
        excluded = [entry for entry in analysed if entry['exclusion']]
        self.stdout.write(f'\n\nWHAT REACHES THE CV PROMPT, OF ALL {len(analysed):,} ENTRIES (TASK-236)')
        self.stdout.write(f'  reaching  {len(reaching):>5} entries  {_chars(reaching):>9,} chars  sent as durable preferences, '
                          'as far as the budget goes')
        self.stdout.write(f'  excluded  {len(excluded):>5} entries  {_chars(excluded):>9,} chars  not sent as durable preferences')
        self.stdout.write('  EXCLUDED IS NOT A VERDICT ON THE ENTRY. It is a mechanical fact about how long the text is and')
        self.stdout.write(f'  about the {WIRE_INSTRUCTION_CAP:,}-char cap the readjustment box applies (views.py:2043). It says the entry is')
        self.stdout.write('  shaped like a one-off brief, never that it is untrue or unimportant -- an excluded entry can be the')
        self.stdout.write('  most important thing in this field. Nothing is deleted: the stored field still holds every entry,')
        self.stdout.write('  each is printed above with its own reason, and --prompt excluded pages through exactly those.')

    def _print_conflicts(self, analysed, chars):
        pairs, duplicates, compared = _conflict_pairs(analysed)
        # Over the whole field, never over the page: entry 3 can contradict entry 40, and a pair that
        # only showed up when both halves happened to land in the same sitting would be worthless.
        self.stdout.write('\n\nPOSSIBLE CONTRADICTIONS -- same subject, opposite request, whole field (AC5)')
        self.stdout.write(f'  A repeat is not a contradiction. Of the {compared:,} entries compared pairwise, {duplicates:,} pair(s) '
                          f'were at least {NEAR_DUP_RATIO:.0%}')
        self.stdout.write('  similar (difflib, the rule report_cv_prompt_size --learned already uses) and were dropped as duplicates,')
        self.stdout.write('  and a pair naming the same size for the same thing is read as agreement however opposite its verbs look.')
        if not pairs:
            self.stdout.write('  No pair left that is about the same subject and asks for opposite things.')
            return
        self.stdout.write(f'  {len(pairs):,} pair(s) left. Each is a CANDIDATE: read both and decide, the rule cannot.')
        for first, second, reasons, shared in pairs:
            subjects = ', '.join(first['subjects'].get(stem, stem) for stem in shared[:8])
            self.stdout.write(_console_safe(f'\n  #{first["index"]} vs #{second["index"]}  -- both about: {subjects}'))
            for reason in reasons:
                self.stdout.write(_console_safe(f'      {reason}'))
            for entry in (first, second):
                self.stdout.write(_console_safe(f'      #{entry["index"]:<4}: {self._excerpt(entry["line"], chars)}'))

    def handle(self, *args, **opts):
        user = _resolve_user(opts['user'] or (settings.CODEX_CV_OWNER_EMAIL or '').strip())
        if not user:
            raise CommandError('No such account. Pass --user with an email, username or id (CODEX_CV_OWNER_EMAIL did not resolve).')
        # filter().first(), not user_profile_settings(): that one is a get_or_create, and a read-only
        # review must not create a row on the owner's database.
        profile = UserProfile.objects.filter(user=user).first()
        if not profile:
            raise CommandError(f'{user} has no profile row, so there are no learned preferences to review.')

        entries = _learned_entries(profile.learned_application_preferences)
        if not entries:
            self.stdout.write(_console_safe(f'{user} has no learned application preferences: there is nothing to review.'))
            return
        evidence, source = _evidence(profile)
        evidence_tokens = set(re.findall(r'[\w+#]+', evidence.casefold()))
        analysed = [_analyse(index, scope, line, evidence_tokens)
                    for index, (scope, line) in enumerate(entries, start=1)]

        self.stdout.write(_console_safe(f'Learned application preferences for {user} -- {len(analysed):,} entries, '
                                        f'{len(profile.learned_application_preferences):,} chars stored'))
        self.stdout.write('Read-only: nothing is written, no provider is launched, and the stored field is untouched.')
        self.stdout.write(_console_safe(f'Terms are checked against {source}, after the same compaction the prompt applies --'))
        self.stdout.write('the source load_candidate_evidence actually reads, which is not always the profile field.')
        self.stdout.write('#1 is the FIRST line in the field; the prompt tells the model that later entries override earlier ones.')

        self.stdout.write('\nHOW TO READ THE LABEL -- it is a sort key, not a verdict')
        self.stdout.write('  The label has NO measured accuracy. It has never been checked against a labelled sample, because')
        self.stdout.write('  no labelled sample exists, and it cannot be honest at the entry level anyway: TASK-225 measured')
        self.stdout.write('  these entries at 67-4,979 chars, median 1,521, so one entry can be a whole pasted readjustment')
        self.stdout.write("  brief that asserts a style preference AND a fact in the same breath. That is TASK-229 AC3's")
        self.stdout.write('  second branch -- the distinction is NOT drawn automatically here, and this tool does not pretend')
        self.stdout.write('  to. What is mechanical is the SIGNAL under each entry: which writing verbs it contains, and which')
        self.stdout.write('  of its distinctive terms appear nowhere in the evidence. Read the signals. An absent term is not')
        self.stdout.write('  a false claim either -- it can be a company from a posting or a technology named as a target,')
        self.stdout.write('  which is why AC1 reported 381 as an upper bound rather than as a count of unsupported claims.')

        wanted, reach = opts['label'], opts['prompt']
        by_flag = {'fact': LABEL_FACT, 'style': LABEL_STYLE, 'unclear': LABEL_UNCLEAR}
        selected = [entry for entry in analysed
                    if (wanted == 'all' or entry['label'] == by_flag[wanted])
                    and (reach == 'all' or bool(entry['exclusion']) == (reach == 'excluded'))]
        start = max(1, opts['start'])
        page = selected[start - 1:] if opts['limit'] <= 0 else selected[start - 1:start - 1 + opts['limit']]
        labelled = ((f' labelled {wanted}' if wanted != 'all' else '')
                    + (f' {REACH_WORDS[reach]}' if reach != 'all' else ''))
        if not page:
            self.stdout.write(f'\nENTRIES: none at --start {start:,} of {len(selected):,}{labelled}.')
        else:
            more = f'; --start {start + len(page)} for the next sitting' if opts['limit'] > 0 and start + len(page) <= len(selected) else ''
            self.stdout.write(f'\nENTRIES {start:,}-{start + len(page) - 1:,} of {len(selected):,}{labelled}'
                              + (f' (--limit {opts["limit"]}{more})' if opts['limit'] > 0 else ''))
        for entry in page:
            self._print_entry(entry, opts['chars'])

        counts = Counter(entry['label'] for entry in analysed)
        both = sum(1 for entry in analysed if entry['both'])
        self.stdout.write(f'\n\nLABELS OVER ALL {len(analysed):,} ENTRIES')
        self.stdout.write(f'  {LABEL_STYLE:<14}{counts[LABEL_STYLE]:>5}  writing verbs only: no uncorroborated term, no date, no measured quantity')
        self.stdout.write(f'  {LABEL_FACT:<14}{counts[LABEL_FACT]:>5}  at least one of those, and no writing verb at all')
        self.stdout.write(f'  {LABEL_UNCLEAR:<14}{counts[LABEL_UNCLEAR]:>5}  both kinds of signal ({both}) or neither ({counts[LABEL_UNCLEAR] - both})')
        if both:
            self.stdout.write(f'  {both:,} of {len(analysed):,} entries carry BOTH kinds of signal. That is the finding, not a defect in')
            self.stdout.write('  the rule: those have to be split by hand before anything can be moved into candidate evidence (AC2).')

        self._print_reach(analysed)
        self._print_conflicts(analysed, opts['chars'])
