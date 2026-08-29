from pathlib import Path


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
