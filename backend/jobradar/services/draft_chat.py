"""TASK-122 ACs 2-10 -- the multi-turn conversation that revises a mailbox reply draft, and the
in-app model choice it runs on.

update_draft_text() (mailbox.py, AC1) already lets the owner rewrite a draft's text by hand and save
it -- the floor this whole feature rests on. This module adds the model-assisted half: a back-and-
forth conversation ("kuerzer" -> "actually keep the date I just added" -> "perfekt") that proposes a
revision for the owner to look at before anything is written anywhere.

Design constraint (from the task brief, not incidental): `claude --print --no-session-persistence`
and Ollama's one-shot `POST /api/generate` are both STATELESS -- neither provider remembers a prior
turn. "Multi-turn" therefore means THIS APP owns the transcript and re-feeds it whole on every call
(see _build_chat_prompt): each turn is handed the original draft, every earlier (instruction,
revision) pair, and the new instruction, and is asked to return the complete revised draft again, not
a diff.

Model choice (AC3) reuses cv_generator's existing machine-capability probe
(`available_model_options`/`validate_model_capability`) rather than a second one. LLM_PROVIDER/
LLM_MODEL/LLM_BASE_URL/LLM_STRICT (interview_coach._load_llm_config, imported here only for its
`.timeout_seconds` default -- see AC9 in .env.local.example) still govern the SEPARATE, existing,
env-only automated classify/draft-generation path in mailbox.py; they are unrelated to which model
THIS interactive conversation uses, which is chosen per call from what `available_model_options()`
says the machine can actually run right now.

Every provider call is a CLI subprocess (`claude` or `codex`, mirroring cv_generator.
generate_cv_package's inner `generate()` -- see cv_generator.py:759-781, the reference this mirrors)
with an explicit timeout (AC8) and is never allowed to raise out of run_chat_turn: a missing binary,
a timed-out process, a non-zero exit, and a malformed/missing JSON response are all caught and turned
into a human-readable `reason` (AC7) -- the same '' -success / non-empty-string-refusal shape
update_draft_text already uses. The revised text is also re-run through mailbox.check_guardrails
(AC6) before it is ever reported as safe to accept -- the same salary-floor/do-not-disclose check a
template-generated draft cannot get past either, so a model cannot talk its way around a rule the
template could not.

This module never persists anything and never touches Gmail -- no MailboxDraft, no request, no view
lives here. The next wave needs, to finish ACs 4/5:
  * a place to persist `history` (a JSON list of {"user_message": ..., "revised_text": ...}) per
    draft, e.g. a MailboxDraft.chat_history JSONField or a sibling model -- see ChatTurn below for
    the exact shape to (de)serialize into/out of;
  * a place to persist the chosen (provider, model) per user (AC4: "must not reset on every mount",
    unlike CV generation's picker), e.g. two UserProfile fields alongside the existing
    mailbox_salary_floor_eur/mailbox_do_not_disclose settings;
  * a view action that calls run_chat_turn() for a turn, shows the owner ChatTurnResult.revised_text
    (only when .reason == '') before anything is written, and on accept calls
    mailbox.update_draft_text(draft, result.revised_text, user=...) to do AC5's Gmail-plus-database
    write. update_draft_text re-runs check_guardrails itself on the accepted text, which is not
    redundant with this module's own guardrail check -- it is the same defense-in-depth this
    codebase already applies twice over for update_draft_text's own edited-by-hand path.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from jobradar.services.cv_generator import CLAUDE_EFFORTS, available_model_options, validate_model_capability
from jobradar.services.interview_coach import _load_llm_config
from jobradar.services.mailbox import _effective_do_not_disclose, _effective_salary_floor_eur, check_guardrails

__all__ = ['ChatTurn', 'ChatTurnResult', 'run_chat_turn', 'available_model_options']


@dataclass
class ChatTurn:
    """One exchange already on record: what the owner asked for, and the draft it produced. The
    complete transcript (not just the latest turn) is what gets re-fed on every subsequent call --
    see the module docstring's stateless-provider note. Field names match 1:1 what the next wave
    should persist as JSON (see the module docstring's AC4/AC5 wiring notes), so a stored item can be
    reconstructed with `ChatTurn(**item)`.
    """
    user_message: str
    revised_text: str


@dataclass
class ChatTurnResult:
    """revised_text is what the model produced -- '' if the call failed before producing anything.
    reason is '' when revised_text is clear to show the owner as accept-ready; any other value means
    it is NOT -- a provider failure (AC7) or a guardrail block (AC6) -- and the caller must not
    persist or write revised_text anywhere in that case, only display the reason.
    """
    revised_text: str
    reason: str


_CHAT_SCHEMA = {
    'type': 'object',
    'properties': {'revised_text': {'type': 'string'}},
    'required': ['revised_text'],
    'additionalProperties': False,
}


def _build_chat_prompt(original_draft_text: str, history: list[ChatTurn], user_message: str) -> str:
    """The whole transcript, re-sent every turn -- see the module docstring's stateless-provider
    note. `history` is TRUSTED (the owner's own prior instructions and the model's own prior
    revisions, never inbound-email text), so unlike sanitize_inbound_text's callers this needs no
    injection scrubbing.
    """
    turns = [
        f'Turn {index} -- owner said: "{turn.user_message}"\nTurn {index} -- resulting draft:\n{turn.revised_text}'
        for index, turn in enumerate(history, start=1)
    ]
    conversation = '\n\n'.join(turns) if turns else '(no earlier turns yet)'
    current_text = history[-1].revised_text if history else original_draft_text
    return (
        'You are revising a short email reply draft for a DACH-focused job-search tracker, at the '
        "candidate's own spoken direction. Apply ONLY the new instruction below to the current draft; "
        'keep everything the earlier turns already settled unless the new instruction changes it.\n\n'
        f'ORIGINAL DRAFT (before any conversation):\n{original_draft_text}\n\n'
        f'CONVERSATION SO FAR:\n{conversation}\n\n'
        f'CURRENT DRAFT (what you must revise from):\n{current_text}\n\n'
        f'NEW INSTRUCTION FROM THE CANDIDATE:\n{user_message}\n\n'
        'Return only valid JSON with this exact shape: {"revised_text": "the complete revised draft, not a diff"}'
    )


def _binary_for(provider: str) -> str | None:
    """The CLI this provider is dispatched through. Split out as its own name (rather than an inline
    shutil.which call) so tests can stub "binary not installed" without touching the real PATH.
    """
    if provider == 'anthropic':
        return shutil.which('claude') or shutil.which('claude.exe')
    return shutil.which('codex') or shutil.which('codex.cmd')


def _run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run, split out as its own name so tests can stub the model process (non-zero exit,
    malformed output, subprocess.TimeoutExpired) without ever spawning a real one (AC7/AC10).
    """
    return subprocess.run(command, **kwargs)


def _run_provider_turn(provider: str, model: str, effort: str, speed: str, model_option: dict, prompt: str, timeout_seconds: float) -> tuple[str, str]:
    """(revised_text, reason). Never raises -- every subprocess/parsing failure becomes a reason
    (AC7): binary missing, timeout, non-zero exit, and malformed/missing JSON are each covered.
    """
    binary = _binary_for(provider)
    if not binary:
        cli_name = 'claude' if provider == 'anthropic' else 'codex'
        return '', f'the {cli_name} CLI is not installed on this machine'

    with tempfile.TemporaryDirectory(prefix='dachapply-draft-chat-') as temp:
        output = Path(temp)
        try:
            if provider == 'anthropic':
                command = [binary, '--print', '--model', model, '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(_CHAT_SCHEMA)]
                if effort in CLAUDE_EFFORTS:
                    command += ['--effort', effort]
                if speed == 'fast':
                    # There is no --fast flag; fastMode is a settings key (see cv_generator.generate_cv_package).
                    command += ['--settings', json.dumps({'fastMode': True})]
                result = _run(command, cwd=output, input=prompt, capture_output=True, text=True, encoding='utf-8', timeout=timeout_seconds, check=False)
                if result.returncode:
                    return '', f'the model process exited with an error: {(result.stderr or result.stdout or "no output").strip()[:500]}'
                response = json.loads(result.stdout)
                structured = response.get('structured_output')
                if not structured and response.get('result'):
                    structured = json.loads(response['result'])
            else:
                schema_path = output / 'schema.json'
                result_path = output / 'result.json'
                schema_path.write_text(json.dumps(_CHAT_SCHEMA), encoding='utf-8')
                command = [binary, 'exec', '--ephemeral', '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check', '--sandbox', 'read-only', '--model', model]
                if provider == 'openai':
                    command += ['--config', f'model_reasoning_effort="{effort}"']
                    if speed == 'fast' and model_option.get('fast_tier'):
                        command += ['--config', f'service_tier="{model_option["fast_tier"]}"']
                else:
                    command += ['--oss', '--local-provider', provider]
                command += ['--cd', str(output), '--output-schema', str(schema_path), '--output-last-message', str(result_path), '-']
                result = _run(command, input=prompt, capture_output=True, text=True, encoding='utf-8', timeout=timeout_seconds, check=False)
                if result.returncode or not result_path.is_file():
                    return '', f'the model process exited with an error: {(result.stderr or result.stdout or "no output").strip()[:500]}'
                structured = json.loads(result_path.read_text(encoding='utf-8'))
            if not isinstance(structured, dict):
                raise ValueError('malformed structured response')
            revised = structured.get('revised_text', '')
        except subprocess.TimeoutExpired:
            return '', f'the model did not respond within {timeout_seconds:.0f}s'
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return '', f'the model returned something this app could not use: {exc}'

    if not isinstance(revised, str) or not revised.strip():
        return '', 'the model returned an empty or invalid revision'
    return revised.strip(), ''


def run_chat_turn(
    original_draft_text: str,
    history: list[ChatTurn],
    user_message: str,
    provider: str,
    model: str,
    effort: str,
    speed: str = 'normal',
    *,
    profile=None,
    timeout_seconds: float | None = None,
) -> ChatTurnResult:
    """One turn of the conversation. Never raises (AC7): an unavailable model (AC3), a provider
    crash, and a guardrail block (AC6) all come back as ChatTurnResult.reason rather than an
    exception. Only a result with reason == '' is safe to show the owner as accept-ready; the caller
    decides whether/when to append the returned turn onto its own persisted `history` (see the module
    docstring's AC4/AC5 wiring notes) and must never write revised_text anywhere until the owner
    explicitly accepts it.

    `timeout_seconds` defaults to the existing LLM_TIMEOUT_SECONDS env var (AC9,
    interview_coach._load_llm_config) rather than a second knob for the same thing; pass it
    explicitly to override per call. AC8's "cannot hang forever" requirement is satisfied either way:
    a timeout always reaches the subprocess call, whichever value it resolved to.
    """
    try:
        model_option = validate_model_capability(provider, model, effort, speed)
    except ValueError as exc:
        return ChatTurnResult('', str(exc))

    resolved_timeout = timeout_seconds if timeout_seconds is not None else _load_llm_config().timeout_seconds
    prompt = _build_chat_prompt(original_draft_text, history, user_message)
    revised_text, reason = _run_provider_turn(provider, model, effort, speed, model_option, prompt, resolved_timeout)
    if reason:
        return ChatTurnResult(revised_text, reason)

    # AC6: the same code-level guardrail a template-generated draft cannot get past either -- run
    # here, on the generated text, never as an instruction the model itself could be talked out of.
    block_reason = check_guardrails(revised_text, _effective_salary_floor_eur(profile), _effective_do_not_disclose(profile))
    return ChatTurnResult(revised_text, block_reason)
