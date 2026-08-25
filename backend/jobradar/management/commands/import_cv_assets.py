"""TASK-99a AC3: move one account's LaTeX templates and photograph out of the workspace into rows.

Dry run by default (CLAUDE.md: a bulk data change gets a dry-run-by-default management command,
never a migration, so a human can inspect what would change before anything is written). It prints
a before/after census -- every asset, its size and its sha256 prefix, as it is now and as it would
be -- and writes nothing until --apply.

Not a data migration on purpose, twice over. A migration would run unattended on every deployment
including production, where CODEX_CV_WORKSPACE is empty and none of these files exist; and it would
have to guess which account the files belong to, which is the exact question this task exists to
stop guessing. The account is named on the command line.

TASK-189 made running this optional rather than necessary: cv_generator reads the same workspace,
for the same one account, when that account has no rows -- so the owner no longer has to put their
photograph in a hosted database to generate locally. This command stays because storing the assets
is still the only thing that works for an account without a workspace of its own, and because a
stored row wins over the workspace, so importing is how you pin a template against later edits.
The layout both readers share lives in services/cv_workspace.py.
"""
import hashlib
import sys

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from jobradar.models import CvAsset
from jobradar.services.cv_workspace import asset_payload, discover


def _digest(payload):
    return hashlib.sha256(payload).hexdigest()[:12]


def _console_safe(text):
    """The Windows console is cp1252 and raises on anything it cannot encode.

    Template filenames are the owner's own and have carried umlauts before, so a census line must
    never be the reason the command dies. Only characters the real console rejects are replaced.
    """
    encoding = getattr(sys.stdout, 'encoding', '') or 'utf-8'
    return text.encode(encoding, 'replace').decode(encoding, 'replace')


class Command(BaseCommand):
    help = (
        "TASK-99a AC3: import an account's LaTeX templates and photograph from a workspace "
        'directory into per-account CvAsset rows, so generation stops resolving them from a path '
        'that exists on one machine. Dry run by default; --apply writes. Re-running is safe and is '
        'how a template edited in the workspace is refreshed: matching rows are updated in place.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--user', required=True, help='Username or email of the account the templates and photo belong to.')
        parser.add_argument('--workspace', default='', help=f'Directory to read from. Defaults to settings.CODEX_CV_WORKSPACE ({settings.CODEX_CV_WORKSPACE or "unset"}).')
        parser.add_argument('--apply', action='store_true', help='Actually write the rows. Without it the command only prints the before/after census.')

    def handle(self, *args, **opts):
        User = get_user_model()
        matches = list(User.objects.filter(Q(username__iexact=opts['user']) | Q(email__iexact=opts['user'])))
        if len(matches) != 1:
            raise CommandError(f'--user {opts["user"]!r} matched {len(matches)} accounts; name exactly one.')
        user = matches[0]

        workspace = Path(opts['workspace'] or settings.CODEX_CV_WORKSPACE or '')
        if not opts['workspace'] and not settings.CODEX_CV_WORKSPACE:
            raise CommandError('No workspace to read: pass --workspace, or set CODEX_CV_WORKSPACE.')
        if not workspace.is_dir():
            raise CommandError(f'Workspace {workspace} is not a directory.')

        found, missing = discover(workspace, user)
        before = {(asset.kind, asset.key): asset for asset in CvAsset.objects.filter(user=user)}

        self.stdout.write(f'Account: {user.get_username()} (id {user.pk})')
        self.stdout.write(f'Workspace: {workspace}')
        self.stdout.write('')
        self.stdout.write(f'{"kind":<7} {"key":<22} {"before":<26} {"after":<26} file')
        for candidate in found:
            existing = before.pop((candidate.kind, candidate.key), None)
            self.stdout.write(_console_safe(
                f'{candidate.kind:<7} {candidate.key or "-":<22} '
                f'{self._census(existing):<26} {self._census(candidate):<26} '
                f'{Path(candidate.source_path).relative_to(workspace)}'
            ))
        for (kind, key), existing in before.items():
            # Stored rows the workspace has nothing for. Left exactly as they are -- this command
            # imports, it never deletes an account's only copy of something.
            self.stdout.write(f'{kind:<7} {key or "-":<22} {self._census(existing):<26} {"(kept, not in workspace)":<26}')
        for label in missing:
            self.stdout.write(self.style.WARNING(f'missing in workspace: {label}'))

        if not opts['apply']:
            self.stdout.write('')
            self.stdout.write(f'Dry run: {len(found)} asset(s) would be written for {user.get_username()}. Nothing changed. Re-run with --apply.')
            return

        written = 0
        for candidate in found:
            # The discovered rows are unsaved instances; this is the one place they are persisted,
            # and it is per account, named on the command line, and never automatic.
            _, created = CvAsset.objects.update_or_create(
                user=user, kind=candidate.kind, key=candidate.key,
                defaults={
                    'language': candidate.language,
                    'label': candidate.label,
                    'filename': candidate.filename,
                    'source': candidate.source,
                    'image': candidate.image,
                    'source_path': candidate.source_path,
                },
            )
            written += 1
            self.stdout.write(_console_safe(f'{"created" if created else "updated"} {candidate.kind}/{candidate.key or "-"} from {Path(candidate.source_path).name}'))
        after = CvAsset.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(f'Wrote {written} asset(s); {user.get_username()} now has {after}.'))

    def _census(self, asset):
        if not asset:
            return '(none)'
        payload = asset_payload(asset)
        return f'{len(payload)} B {_digest(payload)}'
