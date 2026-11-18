"""TASK-393: bake the owner's most-repeated LaTeX spacing fixes into the stored CV templates.

The Adjust log shows the same two OLD/NEW spacing replacements applied again and again to every
generated CV. Doing it once in the stored template (CvAsset kind=cv, field source) stops the repeats.

Dry run by default (a bulk data change is a command, never a migration): prints per template the
match count of each pair and a unified diff, writes nothing. --apply writes only templates where
EVERY pair's OLD is present, replacing every copy and touching nothing else. Re-running is a no-op
because the OLDs no longer match, which is reported as "nothing to change", not as a failure.
"""
import difflib

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from jobradar.models import CvAsset

# (OLD, NEW): the owner's latest choice per job in adjustments.jsonl (2026-11-18: -2pt in 4 of 9 jobs, all since 11-17; 0pt in 7 of 9).
PAIRS = [
    (r'\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}',
     r'\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-2pt}}'),
    (r'\end{tabular*}\vspace{-7pt}', r'\end{tabular*}\vspace{0pt}'),
]


def bake(source):
    """Return (counts per pair, new source); new source is None unless every OLD matched."""
    counts = [source.count(old) for old, _ in PAIRS]
    if not all(counts):
        return counts, None
    for old, new in PAIRS:
        source = source.replace(old, new)
    return counts, source


class Command(BaseCommand):
    help = 'TASK-393: bake the repeated spacing fixes into stored CV templates. Dry run by default; --apply writes.'

    def add_arguments(self, parser):
        parser.add_argument('--user', default='', help='Username, email or id; limits the run to one account.')
        parser.add_argument('--apply', action='store_true', help='Write the changes. Without it nothing is written.')

    def handle(self, *args, **opts):
        assets = CvAsset.objects.filter(kind=CvAsset.KIND_CV).select_related('user').order_by('user_id', 'key')
        if opts['user']:
            ident = opts['user']
            query = Q(username__iexact=ident) | Q(email__iexact=ident)
            if ident.isdigit():
                query |= Q(pk=int(ident))
            users = list(get_user_model().objects.filter(query))
            if len(users) != 1:
                raise CommandError(f'--user {ident!r} matched {len(users)} accounts; name exactly one.')
            assets = assets.filter(user=users[0])

        written = skipped = unchanged = 0
        for asset in assets:
            name = f'user {asset.user.get_username()} (id {asset.user_id}) cv/{asset.key or "-"} {asset.filename}'
            counts, new = bake(asset.source)
            summary = ', '.join(f'pair {i + 1}: {n} match(es)' for i, n in enumerate(counts))
            self.stdout.write(f'{name}: {summary}')
            if new is None:
                if any(counts):
                    skipped += 1
                    missing = ', '.join(str(i + 1) for i, n in enumerate(counts) if not n)
                    self.stdout.write(f'  skipped: OLD of pair {missing} not found')
                else:
                    unchanged += 1
                    self.stdout.write('  nothing to change')
                continue
            self.stdout.writelines(difflib.unified_diff(
                asset.source.splitlines(keepends=True), new.splitlines(keepends=True),
                'stored', 'baked'))
            if opts['apply']:
                asset.source = new
                asset.save(update_fields=['source'])
                written += 1
        mode = 'Wrote' if opts['apply'] else 'Dry run, would write'
        count = written if opts['apply'] else sum(1 for a in assets if bake(a.source)[1] is not None)
        self.stdout.write(f'{mode} {count} template(s); {skipped} skipped, {unchanged} nothing to change.')
