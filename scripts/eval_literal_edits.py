"""TASK-278 evaluation of the free-form literal-edit route against an installed local model.

Not part of pytest. Runs every case in backend/jobradar/tests/fixtures/literal_edits/cases.json
against the fictional fixture CV through the same steps as the revise endpoint (deterministic
parser, else local model, then the reliability gate) and prints wrong edits applied (must be 0),
coverage of literal cases, and local-model latency. Uses the hermetic test settings (in-memory
sqlite); nothing is written anywhere.

    cd backend && uv run python ../scripts/eval_literal_edits.py --model ollama:gemma3:4b
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / 'backend'
FIXTURES = BACKEND / 'jobradar' / 'tests' / 'fixtures' / 'literal_edits'


def main():
    sys.stdout.reconfigure(encoding='utf-8')  # cases contain '→'; a Windows console defaults to cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='ollama:gemma3:4b', help="'ollama:<name>' or 'lmstudio:<name>'")
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args()
    sys.path.insert(0, str(BACKEND))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_test'
    import django
    django.setup()
    from jobradar.services.cv_generator import match_exact_pair
    from jobradar.services.literal_edits import NotLiteral, deterministic_edit_pairs, gate_literal_edits, translate_literal_edits

    provider, _, model = args.model.partition(':')
    path = str(FIXTURES / 'fictional_cv.tex')
    source = (FIXTURES / 'fictional_cv.tex').read_text(encoding='utf-8')
    cases = json.loads((FIXTURES / 'cases.json').read_text(encoding='utf-8'))

    def expected_text(edits):
        text = source
        for old, new in edits:
            _, start, end, replacement = match_exact_pair({path: text}, old, new)
            text = text[:start] + replacement + text[end:]
        return text

    started = time.perf_counter()
    try:
        translate_literal_edits({path: source}, 'replace "Hamburg" with "Berlin"', provider, model, timeout=120)
    except NotLiteral:
        pass
    print(f'warm-up (model load) {time.perf_counter() - started:.1f}s')

    wrong, handled, literal_total, literal_latency, all_latency = 0, 0, 0, [], []
    for case in cases:
        instruction, expected = case['instruction'], case['edits']
        pairs = deterministic_edit_pairs(instruction)
        route, latency = 'deterministic', None
        try:
            if pairs is None:
                route = 'model'
                began = time.perf_counter()
                try:
                    pairs = translate_literal_edits({path: source}, instruction, provider, model, timeout=args.timeout)
                finally:
                    latency = time.perf_counter() - began
            updates, edits = gate_literal_edits({path: source}, instruction, pairs)
            outcome = updates[path]
        except NotLiteral as exc:
            outcome, edits, reason = None, [], str(exc)
        if latency is not None:
            all_latency.append(latency)
            if expected is not None:
                literal_latency.append(latency)
        applied = outcome is not None
        correct = (not applied) if expected is None else applied and outcome == expected_text(expected)
        if expected is not None:
            literal_total += 1
            handled += bool(correct)
        is_wrong = applied and not correct
        wrong += is_wrong
        verdict = 'WRONG' if is_wrong else 'ok' if correct else 'fallback'
        detail = '; '.join(f'{old!r}->{new!r}' for old, new in edits) if applied else reason
        timing = f'{latency:5.1f}s' if latency is not None else '   - '
        print(f'{verdict:8} {case["category"]:13} {route:13} {timing} {instruction[:60]!r} | {detail[:120]}')
    print(f'\nmodel {args.model}: wrong edits applied {wrong}; coverage {handled}/{literal_total} '
          f'({handled / literal_total:.0%}) literal cases without full optimization')
    for label, values in (('literal cases', literal_latency), ('all model calls', all_latency)):
        if values:
            print(f'local-model latency over {label} (n={len(values)}): median {statistics.median(values):.1f}s, max {max(values):.1f}s')
    return 1 if wrong else 0


if __name__ == '__main__':
    sys.exit(main())
