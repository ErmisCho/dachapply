"""One account's LaTeX templates and photograph, read off a machine-local workspace directory.

Split out of the import_cv_assets management command by TASK-189, which gave the historic layout a
second reader: cv_generator falls back to the workspace for an account that has no stored CvAsset
rows (see cv_generator.user_cv_assets for the precedence rule and why it exists). The layout lives
here once rather than in both callers.

Nothing here writes to the database. `discover` returns UNSAVED CvAsset instances -- the same shape
the stored rows have, so a caller reads either identically -- and import_cv_assets is the only
caller that ever saves one. That is deliberate: generation must be able to read the owner's files
without their name, address, phone and a 1.2 MB photograph of their face ending up in a database
that gets backed up somewhere else (TASK-189 AC2).
"""
import re
from pathlib import Path

from jobradar.models import CvAsset

# (relative path in the workspace, label). Base CVs are versioned as "<name>_v_<major>.<minor>.tex"
# and the newest on disk wins; the path here is only the pattern's starting point.
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


def _read_text(path):
    """The template's text, or None when the file is unreadable rather than absent.

    Unreadable counts as missing on purpose. This runs on every preview request now, and the
    workspace is a directory the owner edits by hand: a half-written file mid-save is a plausible
    UnicodeDecodeError, and a 500 on the board is a worse answer than one template being absent
    until the save finishes.
    """
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None


def discover(workspace, user=None):
    """(assets, missing) for `workspace`: unsaved CvAsset rows, and the labels of what is absent.

    `user` is set on the returned instances so a caller reads ownership the same way it does on a
    stored row. They are never saved -- see the module docstring.
    """
    found, missing = [], []
    for language, layout in WORKSPACE_LAYOUT.items():
        relative, label = layout['cv']
        path = latest_versioned(workspace, relative)
        source = _read_text(path) if path.is_file() else None
        if source is not None:
            found.append(CvAsset(user=user, kind=CvAsset.KIND_CV, key=language, language=language, label=label,
                                 filename=path.name, source=source, image=b'', source_path=str(path)))
        else:
            missing.append(f'{label} ({relative})')
        for key, (letter_relative, letter_label) in layout['letters'].items():
            letter_path = workspace / letter_relative
            letter_source = _read_text(letter_path) if letter_path.is_file() else None
            if letter_source is not None:
                found.append(CvAsset(user=user, kind=CvAsset.KIND_LETTER, key=key, language=language, label=letter_label,
                                     filename=letter_path.name, source=letter_source, image=b'', source_path=str(letter_path)))
            else:
                missing.append(f'{letter_label} ({letter_relative})')
    photo = workspace / PHOTO_PATH
    try:
        image = photo.read_bytes() if photo.is_file() else None
    except OSError:
        image = None
    if image is not None:
        # filename stays Picture.jpg because that is the name the CV templates' own
        # \includegraphics line already uses; renaming it means editing them.
        found.append(CvAsset(user=user, kind=CvAsset.KIND_PHOTO, key='', language='', label='Photograph',
                             filename=photo.name, source='', image=image, source_path=str(photo)))
    else:
        missing.append(f'Photograph ({PHOTO_PATH})')
    return found, missing


def asset_payload(asset):
    """The bytes an asset actually carries, template or photograph, for sizing and hashing."""
    return bytes(asset.image) if asset.kind == CvAsset.KIND_PHOTO else asset.source.encode('utf-8')
