"""TASK-343: a target file open in another program (Foxit held a CV PDF on 2026-10-22) stops the write
before anything changes, with a message naming the file."""
from pathlib import Path

import pytest

from jobradar.services import cv_generator
from jobradar.services.cv_generator import FileLocked, _ensure_writable, persist_generated_files


def _lock(monkeypatch, locked_name):
    real_open = Path.open

    def fake_open(self, mode='r', *args, **kwargs):
        if self.name == locked_name and 'r+' in mode:
            raise PermissionError(13, 'Permission denied')
        return real_open(self, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fake_open)


def test_a_locked_file_is_named_and_a_free_or_missing_one_passes(tmp_path, monkeypatch):
    free, locked = tmp_path / 'cv.tex', tmp_path / 'cv.pdf'
    free.write_text('x'); locked.write_bytes(b'%PDF')
    _lock(monkeypatch, 'cv.pdf')
    _ensure_writable([free, tmp_path / 'missing.pdf'])
    with pytest.raises(FileLocked, match='cv.pdf is open in another program'):
        _ensure_writable([free, locked])


def test_generation_writes_nothing_when_a_target_is_locked(tmp_path, monkeypatch, settings):
    workspace, output = tmp_path / 'ws', tmp_path / 'out'
    (workspace / 'CVs').mkdir(parents=True); (workspace / 'output').mkdir(); output.mkdir()
    for name, body in (('cv.tex', 'new cv'), ('cv.pdf', 'new pdf'), ('letter.tex', 'new letter'), ('letter.pdf', 'new lpdf')):
        (output / name).write_text(body)
    cv_target, letter_target = workspace / 'CVs' / 'cv.tex', workspace / 'output' / 'letter.tex'
    for path in (cv_target, cv_target.with_suffix('.pdf'), letter_target, letter_target.with_suffix('.pdf')):
        path.write_text('old')
    monkeypatch.setattr(cv_generator, '_sent_paths', lambda workspace: set())
    _lock(monkeypatch, 'letter.pdf')
    with pytest.raises(FileLocked):
        persist_generated_files(output, workspace, 'cv.tex', 'letter.tex', str(cv_target), str(letter_target))
    assert cv_target.read_text() == 'old' and cv_target.with_suffix('.pdf').read_text() == 'old'  # nothing half-written
