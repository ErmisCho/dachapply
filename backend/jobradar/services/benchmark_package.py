"""TASK-369: opt-in package comparison; production generation stays unchanged."""
from pathlib import Path
import shutil
from time import time

from django.conf import settings
from django.core.management.base import CommandError
from django.test.utils import override_settings

from jobradar.services import application_prep as prep, cv_tasks


def package(jobs, user, workers, variant):  # TASK-369
    if variant not in (None, 'separate', 'combined'):
        raise CommandError('package variants: separate, combined (omit to compare both).')
    states = [{'variants': {}} for job in jobs]
    root = Path(settings.CODEX_CV_WORKSPACE)
    for arm in ([variant] if variant else ['separate', 'combined']):
        workspace = root / arm
        shutil.copytree(root, workspace, dirs_exist_ok=True, ignore=lambda path, names: ['separate', 'combined'] if Path(path) == root else [])
        # TASK-369: isolate sidecars/cache and fresh filenames between comparison arms.
        with override_settings(CODEX_CV_WORKSPACE=str(workspace), CODEX_CV_CACHE=False):
            for job, state in zip(jobs, states):
                job_started = time()
                reason, planned, context, choice = prep._gate(job, user)
                if reason:
                    state['reason'] = reason
                    continue
                previous = prep._state(job, user).get('variants', {})
                variants = {v['key']: {**v, **previous.get(v['key'], {})} for v in planned}
                pending = [v for v in variants.values() if v.get('status') != 'ready' or not prep._files_present(v)]
                groups = []
                while pending:
                    item = pending.pop(0)
                    letters = [v for v in pending if arm == 'combined' and item['document'] == 'cv' and v.get('recommended') and v['document'] == 'letter']
                    pair = next((v for v in letters if v['language'] == item['language']), letters[0] if letters else None)
                    group = [item, pair] if pair else [item]
                    if pair:
                        pending.remove(pair)
                    groups.append(group)
                for group in groups:
                    cv = next((v for v in group if v['document'] == 'cv'), None)
                    letter = next((v for v in group if v['document'] != 'cv'), None)
                    started = time()
                    try:
                        _, _, saved = cv_tasks.generate_cv_package(job, context, group[0]['language'],
                            letter.get('letter_template', '') if letter else '', bool(letter), **choice,
                            create_cv=bool(cv), user_id=user.pk, short_message=bool(letter and letter['document'] == 'message'),
                            name_suffix=prep._name_suffix(letter or cv, variants))
                        for item in group:
                            kind = 'cv' if item['document'] == 'cv' else 'letter'
                            item.update(status='ready', files={k: v for k, v in saved.items() if k in (kind+'_tex', kind+'_pdf')})
                    except Exception as exc:
                        from jobradar.services.cv_generator import GenerationCancelled
                        for item in group:
                            item.update(status='cancelled' if isinstance(exc, GenerationCancelled) else 'failed', error=str(exc)[:500])
                    for item in group:
                        item.update(finished_at=prep._now(), elapsed_seconds=time()-started, arm=arm)
                    prep._save(job, user.pk, lambda data: data.update(variants=variants, model=choice))
                state['variants'].update({arm+':'+key: {**value, 'arm': arm} for key, value in variants.items()})
                state.setdefault('package_seconds', {})[arm] = time()-job_started
    return states


def review(result, output):  # TASK-369: no generated evidence dumps; owner judges PDFs.
    lines = ['# Package comparison', '', 'Keep production defaults pending owner quality review. Unrun arms have no documents.', 'When both arms run in one invocation, summary.md metrics span both arms; use the per-arm figures here.', '',
             '| Measure | separate | combined |', '|---|---|---|']
    for label, measure in [('Requests', lambda rows: len(rows)), ('Elapsed request seconds', lambda rows: round(sum(r['end']-r['start'] for r in rows), 3)),
                           ('Failures', lambda rows: sum(r['status'] != 'success' for r in rows)), ('Repairs', lambda rows: sum(r['repair'] for r in rows))]:
        values = [str(measure([r for r in result['requests'] if r.get('package_arm') == arm])) for arm in ('separate', 'combined')]
        lines.append(f'| {label} | '+ ' | '.join(values)+' |')
    lines.append('| Elapsed seconds | '+' | '.join(f"{sum(s.get('package_seconds', {}).get(arm, 0) for s in result['states']):.3f}" for arm in ('separate', 'combined'))+' |')
    artifacts = {a['path']: a for a in result['artifacts']}
    for original, scratch in result['job_mapping'].items():
        state = result['states'][list(result['job_mapping'].values()).index(scratch)]
        lines += ['', f'## Job {original}', '', '| Document | separate | combined |', '|---|---|---|']
        lines.append('| Elapsed seconds | '+' | '.join(f"{state.get('package_seconds', {}).get(arm, 0):.3f}" for arm in ('separate', 'combined'))+' |')
        lines.append('| Failed/cancelled documents | '+' | '.join(str(sum(v.get('status') in ('failed', 'cancelled') for v in state['variants'].values() if v.get('arm') == arm)) for arm in ('separate', 'combined'))+' |')
        counts = []
        for arm in ('separate', 'combined'):
            rows = [r for r in result['requests'] if r.get('job_id') == scratch and r.get('package_arm') == arm]
            counts.append(f"{len(rows)} / {sum(r['repair'] for r in rows)} / {sum(r['end']-r['start'] for r in rows):.3f}")
        lines.append('| Requests / repairs / request seconds | '+' | '.join(counts)+' |')
        keys = sorted({key.split(':', 1)[1] for key in state['variants']})
        for key in keys:
            cells = []
            for arm in ('separate', 'combined'):
                item = state['variants'].get(arm+':'+key, {})
                paths = [f"[{Path(p).name}]({p}) ({artifacts.get(p, {}).get('pages', 'unknown')} pages)" for k, p in item.get('files', {}).items() if k.endswith('_pdf')]
                cells.append(f"{item.get('status', 'not run')}; language {item.get('language', '?')}; limit {2 if item.get('document') == 'cv' else 1} pages; "+'; '.join(paths))
            lines.append(f'| {key} | '+' | '.join(cells)+' |')
        lines += ['', 'For each arm: [ ] page limit met [ ] language correct [ ] layout compiled [ ] factual accuracy checked',
                  'Manual corrections (separate / combined): ______ / ______', 'Owner quality decision: ______']
    (output / 'review.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


package.review = review  # TASK-369
