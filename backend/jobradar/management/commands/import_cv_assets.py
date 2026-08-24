"""TASK-99a AC3: move one account's LaTeX templates and photograph out of the workspace into rows.

Dry run by default (CLAUDE.md: a bulk data change gets a dry-run-by-default management command,
never a migration, so a human can inspect what would change before anything is written). It prints
a before/after census -- every asset, its size and its sha256 prefix, as it is now and as it would
be -- and writes nothing until --apply.

Not a data migration on purpose, twice over. A migration would run unattended on every deployment
including production, where CODEX_CV_WORKSPACE is empty and none of these files exist; and it would
have to guess which account the files belong to, which is the exact question this task exists to
stop guessing. The account is named on the command line.

The historic workspace layout below is the only place it still lives. cv_generator no longer knows
these filenames -- reading that directory is a one-off import now, not a per-request lookup.
"""
import hashlib
import re
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from jobradar.models import CvAsset

# (relative path in the workspace, label). Base CVs are versioned as "<name>_v_<major>.<minor>.tex"
# and the newest on disk wins, which is what cv_generator.latest_cv_template used to do on every
# request; the path here is only the pattern's starting point.
WORKSPACE_LAYOUT = {
    'en': {
        'cv': ('CVs/English - AI Engineer (base)_v_1.3.tex', 'English AI Engineer CV'),
        'letters': {
            'motivation_letter': ('Motivation_letter.tex', 'English motivation letter'),
        },
    },
    'de': {
        'cv': ('CVs/German - AI Engineer (base)_v_1.3.tex', 'German AI Engineer CV'),
        'letters': {
            'motivationsschreiben': ('Motivationsschreiben.tex', 'Motivationsschreiben'),
            'bewerbungsschreiben': ('Bewerbungsschreiben.tex', 'Bewerbungsschreiben'),
            'anschreiben': ('Anschreiben.tex', 'Anschreiben'),
        },
    },
}
PHOTO_PATH = 'CVs/Picture.jpg'


def _version(path):
    match = re.search(r'_v_(\d+(?:\.\d+)*)$', path.stem)
    # An int tuple, so _v_1.10 correctly beats _v_1.9.
    return tuple(int(part) for part in match.group(1).split('.')) if match else ()


def latest_versioned(workspace, relative):
    """The newest _v_ sibling of `relative`, or `relative` itself when none is on disk."""
    base = Path(relative)
    stem = re.sub(r'_v_[\d.]+$', '', base.stem)
    candidates = [path for path in (workspace / base.parent).glob(f'{stem}_v_*.tex') if _version(path)]
    return workspace / base.parent / max(candidates, key=_version).name if candidates else workspace / base


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

        found, missing = self._discover(workspace)
        before = {(asset.kind, asset.key): asset for asset in CvAsset.objects.filter(user=user)}

        self.stdout.write(f'Account: {user.get_username()} (id {user.pk})')
        self.stdout.write(f'Workspace: {workspace}')
        self.stdout.write('')
        self.stdout.write(f'{"kind":<7} {"key":<22} {"before":<26} {"after":<26} file')
        for candidate in found:
            key = (candidate['kind'], candidate['key'])
            existing = before.pop(key, None)
            self.stdout.write(_console_safe(
                f'{candidate["kind"]:<7} {candidate["key"] or "-":<22} '
                f'{self._census(existing):<26} {len(candidate["payload"])} B {_digest(candidate["payload"]):<12} '
                f'{candidate["path"].relative_to(workspace)}'
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
            _, created = CvAsset.objects.update_or_create(
                user=user, kind=candidate['kind'], key=candidate['key'],
                defaults={
                    'language': candidate['language'],
                    'label': candidate['label'],
                    'filename': candidate['filename'],
                    'source': candidate['source'],
                    'image': candidate['image'],
                    'source_path': str(candidate['path']),
                },
            )
            written += 1
            self.stdout.write(_console_safe(f'{"created" if created else "updated"} {candidate["kind"]}/{candidate["key"] or "-"} from {candidate["path"].name}'))
        after = CvAsset.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(f'Wrote {written} asset(s); {user.get_username()} now has {after}.'))

    def _census(self, asset):
        if not asset:
            return '(none)'
        payload = asset.source.encode('utf-8') if asset.kind != CvAsset.KIND_PHOTO else bytes(asset.image)
        return f'{len(payload)} B {_digest(payload)}'

    def _discover(self, workspace):
        """Every template and photo present in the workspace, plus the labels of those that are not."""
        found, missing = [], []
        for language, layout in WORKSPACE_LAYOUT.items():
            relative, label = layout['cv']
            path = latest_versioned(workspace, relative)
            if path.is_file():
                source = path.read_text(encoding='utf-8')
                found.append({'kind': CvAsset.KIND_CV, 'key': language, 'language': language, 'label': label,
                              'filename': path.name, 'source': source, 'image': b'', 'path': path,
                              'payload': source.encode('utf-8')})
            else:
                missing.append(f'{label} ({relative})')
            for key, (letter_relative, letter_label) in layout['letters'].items():
                letter_path = workspace / letter_relative
                if letter_path.is_file():
                    source = letter_path.read_text(encoding='utf-8')
                    found.append({'kind': CvAsset.KIND_LETTER, 'key': key, 'language': language, 'label': letter_label,
                                  'filename': letter_path.name, 'source': source, 'image': b'', 'path': letter_path,
                                  'payload': source.encode('utf-8')})
                else:
                    missing.append(f'{letter_label} ({letter_relative})')
        photo = workspace / PHOTO_PATH
        if photo.is_file():
            image = photo.read_bytes()
            found.append({'kind': CvAsset.KIND_PHOTO, 'key': '', 'language': '', 'label': 'Photograph',
                          # Kept as Picture.jpg because that is the name the CV templates'
                          # \includegraphics line already uses; renaming it means editing them.
                          'filename': photo.name, 'source': '', 'image': image, 'path': photo,
                          'payload': image})
        else:
            missing.append(f'Photograph ({PHOTO_PATH})')
        return found, missing
