"""TASK-290 (Codex model discovery) and TASK-293 (draft model default). A fake models_cache.json under
a tmp CODEX_HOME stands in for the real Codex cache; nothing here runs a CLI.
"""
import json

from jobradar.services import cv_generator
from jobradar.services.draft_chat import default_draft_choice

LEVELS = [{'effort': e} for e in ('low', 'medium', 'high', 'xhigh', 'max', 'ultra')]
FAST = [{'id': 'priority', 'name': 'Fast'}]


def _cache(tmp_path, monkeypatch, models):
    (tmp_path / 'models_cache.json').write_text(json.dumps({'models': models}), encoding='utf-8')
    monkeypatch.setenv('CODEX_HOME', str(tmp_path))


def test_codex_options_follow_codex_priority_with_per_model_effort_and_fast(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, [
        {'slug': 'gpt-5.6-sol', 'visibility': 'list', 'priority': 5, 'supported_reasoning_levels': LEVELS, 'default_reasoning_level': 'low', 'service_tiers': FAST},
        {'slug': 'gpt-6-luna', 'display_name': 'GPT-6-Luna', 'visibility': 'list', 'priority': 4, 'supported_reasoning_levels': LEVELS[:5], 'default_reasoning_level': 'medium', 'service_tiers': []},
        {'slug': 'gpt-6.1-sol', 'display_name': 'GPT-6.1-Sol', 'visibility': 'list', 'priority': 1, 'supported_reasoning_levels': LEVELS, 'default_reasoning_level': 'low', 'service_tiers': FAST},
        {'slug': 'gpt-reserve', 'visibility': 'hide', 'priority': 2, 'supported_reasoning_levels': LEVELS},
        {'slug': 'codex-auto-review', 'visibility': 'list', 'priority': 3, 'supported_reasoning_levels': LEVELS},
    ])
    options = cv_generator.codex_model_options()
    assert [o['key'] for o in options] == ['gpt-6.1-sol', 'gpt-6-luna', 'gpt-5.6-sol']
    assert options[0]['label'] == 'GPT-6.1-Sol' and options[0]['efforts'][-1] == 'ultra' and options[0]['fast_tier'] == 'priority'
    assert options[1]['efforts'] == ['low', 'medium', 'high', 'xhigh', 'max'] and options[1]['fast_tier'] == ''
    assert not any(o.get('fallback') for o in options)


def test_unreadable_cache_falls_back_and_flags_it(tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_HOME', str(tmp_path))  # no models_cache.json at all
    options = cv_generator.codex_model_options()
    assert options and all(o['fallback'] and o['provider'] == 'openai' for o in options)


def test_draft_default_is_newest_codex_model_at_xhigh():
    options = [
        {'provider': 'openai', 'key': 'gpt-6.1-sol', 'efforts': ['low', 'medium', 'xhigh', 'max'], 'default_effort': 'low'},
        {'provider': 'openai', 'key': 'gpt-6-luna', 'efforts': ['low', 'high'], 'default_effort': 'low'},
        {'provider': 'anthropic', 'key': 'opus', 'efforts': ['low', 'xhigh'], 'default_effort': 'medium'},
    ]
    assert default_draft_choice(options)[:2] == (options[0], 'xhigh')
    # A model without xhigh gets its highest level below it, never max/ultra.
    assert default_draft_choice(options, 'openai', 'gpt-6-luna') == (options[1], 'high', False)
    # A stored model Codex no longer offers falls back to the newest, and says so.
    assert default_draft_choice(options, 'openai', 'gpt-5.4') == (options[0], 'xhigh', True)
