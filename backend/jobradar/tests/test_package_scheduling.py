"""TASK-367: deterministic scheduling experiment; production FIFO stays unless AC5 passes."""
import heapq

import pytest

from jobradar.services import application_prep
from jobradar.tests.test_application_prep import _job, _req, generator, owner, workspace  # noqa: F401


def _measure(monkeypatch, settings, entries, variants, slots, owner, output):  # TASK-367
    """Drive the real pump with a fixed-duration fake generator and virtual completion clock."""
    clock, events, finished, started = [0], [], {}, []
    monkeypatch.setattr(application_prep, '_queue', list(entries))
    monkeypatch.setattr(application_prep, '_running', 0)
    settings.PREP_QUEUE_CONCURRENCY = slots
    monkeypatch.setattr(application_prep, '_document_seconds', lambda prep, variant: 10 if variant['document'] == 'cv' else 20)
    state = application_prep.queue_state(owner)
    waiting = [item for item in state['items'] if item['status'] == 'queued']
    assert [(item['job_id'], owner.pk, item['key']) for item in waiting] == list(entries)
    assert [item['position'] for item in waiting] == list(range(1, len(entries) + 1))
    output.mkdir()

    def start(*entry):
        application_prep._running += 1
        started.append(entry)
        seconds = 10 if variants[entry]['document'] == 'cv' else 20
        heapq.heappush(events, (clock[0] + seconds, len(started), entry))

    monkeypatch.setattr(application_prep, '_start', start)
    application_prep._pump()
    while events:
        clock[0], _, entry = heapq.heappop(events)
        finished[entry] = clock[0]
        (output / f'{entry[0]}-{entry[2]}.tex').write_text(str(entry), encoding='utf-8')
        application_prep._running -= 1
        application_prep._pump()
    assert len(started) == len(set(started)) == len(entries)
    assert set(finished) == set(entries) and not application_prep._queue
    assert len(list(output.glob('*.tex'))) == len(entries)
    assert all(item['eta_seconds'] == finished[item['job_id'], owner.pk, item['key']] for item in waiting)
    assert state['summary']['seconds_left'] == clock[0]
    packages = []
    for job_id, user_id in dict.fromkeys(entry[:2] for entry in entries):
        languages = {variant['language'] for entry, variant in variants.items() if entry[:2] == (job_id, user_id)}
        packages.append(min(max(finished[entry] for entry, variant in variants.items()
                                if entry[:2] == (job_id, user_id) and variant['language'] == language
                                and (variant['document'] != 'letter' or variant['recommended'])) for language in languages))
    return sorted(packages), clock[0], started


@pytest.mark.parametrize('slots', [1, 2])  # TASK-367
@pytest.mark.parametrize('requirement', ['required', 'preferred'])
def test_useful_first_experiment_must_improve_first_package_before_shipping(owner, generator, workspace, monkeypatch, settings, slots, requirement):
    # Capture the real gate's requested variants without starting model work.
    settings.PREP_QUEUE_CONCURRENCY = 0
    jobs = [_job(owner, 'new', requirements=_req('de', cover_letter=requirement)) for _ in range(3)]
    for job in jobs:
        application_prep.prepare(job.id, owner)
    baseline = list(application_prep._queue)
    variants = {(job.id, owner.pk, key): variant for job in jobs
                for key, variant in application_prep._state(job, owner)['variants'].items()}
    assert len(baseline) == 12  # CV + recommended letter + both alternative templates per job
    candidate = sorted(baseline, key=lambda entry: variants[entry]['document'] == 'letter' and not variants[entry]['recommended'])
    before = _measure(monkeypatch, settings, baseline, variants, slots, owner, workspace / 'baseline')
    after = _measure(monkeypatch, settings, candidate, variants, slots, owner, workspace / 'candidate')
    expected = {1: (([30, 100, 170], 210), ([30, 60, 90], 210)),
                2: (([20, 60, 90], 110), ([20, 40, 50], 110))}
    assert before[:2] == expected[slots][0] and after[:2] == expected[slots][1]
    assert before[2] == baseline and after[2] == candidate and before[2] != after[2]
    assert set(before[2]) == set(after[2]) == set(variants)
    # AC5 rejects this candidate: next packages improve, but the first one does not.
    assert after[0][0] == before[0][0]
