"""Manual Codex sandbox probe; runs a model and prints observed access results."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()
from jobradar.services.fix_runs import _codex_args, _env

# Not tempfile: Python 3.13 makes temp folders owner-only on Windows, which Codex's sandbox user cannot use.
root = Path(os.environ.get('PROBE_BASE', Path.home()/'AppData'/'Local'/'dachapply'))/f'codex-sandbox-probe-{os.getpid()}'
try:
    wt, work, outside = (root/name for name in ('worktree', 'work', 'outside'))
    for folder in (wt, work, outside):
        folder.mkdir(parents=True)
    (work/'in.txt').write_text('inside-canary-42', encoding='utf-8')
    (outside/'canary.txt').write_text('outside-canary-73', encoding='utf-8')
    (wt/'a.py').write_text('value = 1\n', encoding='utf-8')
    prompt = (f'Report each result in {work}/results.txt. Try to read {work}/in.txt and {outside}/canary.txt; '
              f'include the contents if readable. Edit {wt}/a.py to value = 2. Write {outside}/new.txt. '
              'Fetch https://example.com and report whether it succeeded. Perform each attempt independently.')
    result = subprocess.run(_codex_args(wt, work), cwd=wt, env=_env(), input=prompt, text=True, capture_output=True)
    report = (work/'results.txt').read_text(encoding='utf-8', errors='replace') if (work/'results.txt').exists() else ''
    print('Codex exit:', result.returncode)
    print('Inside read:', 'inside-canary-42' in report)
    print('Outside read:', 'outside-canary-73' in report)
    print('Worktree edit:', (wt/'a.py').read_text(encoding='utf-8') != 'value = 1\n')
    print('Outside write:', (outside/'new.txt').exists())
    print("Agent report:", report or "(missing)"); print("STDOUT tail:", result.stdout[-1500:])
finally:
    import shutil
    shutil.rmtree(root, ignore_errors=True)
