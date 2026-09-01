import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def test_local_runtime_uses_released_main_without_touching_development_worktree():
    launcher = (ROOT / 'scripts' / 'dachapply-local-runtime.cmd').read_text().lower()
    deploy = (ROOT / '.github' / 'workflows' / 'deploy-container-apps.yml').read_text().lower()

    assert 'worktree add --detach "%runtime%" origin/main' in launcher
    assert 'git -c "%runtime%" reset --hard origin/main' in launcher
    assert 'git -c "%repo%" reset' not in launcher
    assert launcher.index('if not "!local_sha!"=="!main_sha!" goto sync_failed') < launcher.index('python manage.py runserver')
    assert launcher.count('call "%stop_script%"') >= 2
    assert 'branches:\n      - main' in deploy
    assert '--image "$image_name:$github_sha"' in deploy


def test_local_runtime_resolves_ignored_candidate_evidence_from_source_checkout(tmp_path):
    launcher = (ROOT / 'scripts' / 'dachapply-local-runtime.cmd').read_text()
    assert 'set "DACHAPPLY_SOURCE_REPO=%REPO%"' in launcher

    env={**os.environ, 'DEBUG':'True', 'DATABASE_URL':'', 'DACHAPPLY_SOURCE_REPO':str(tmp_path)}
    env.pop('CODEX_CANDIDATE_EVIDENCE_PATH', None)
    result=subprocess.run(
        [sys.executable, '-c', 'from config.settings import CODEX_CANDIDATE_EVIDENCE_PATH; print(CODEX_CANDIDATE_EVIDENCE_PATH)'],
        cwd=ROOT/'backend', env=env, capture_output=True, text=True, check=True,
    )

    assert Path(result.stdout.strip()) == tmp_path/'Ermis-Chorinopoulos-Candidate-Evidence.md'
