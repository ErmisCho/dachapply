"""TASK-104: interview-answer evaluator absorbed from github.com/ErmisCho/ai-interview-coach-dach.

Ported nearly verbatim from the standalone coach's app/analysis.py (a plain-Python module with no
FastAPI/pydantic dependency). One deliberate change from the source: that module loaded its own
.env file at first import (ENV_FILE_CANDIDATES/_load_env_file), duplicating what config/settings.py
already does for the whole Django process before any app code runs. That private loader is dropped
here; _load_llm_config() reads os.environ directly, same as every LLM_PROVIDER-style env gate in
this codebase (see config.settings.CODEX_CV_ENABLED for the same "env var picked up by settings.py's
own .env loading" idiom). Heuristic mode is always available with nothing configured; the local-LLM
modes are opt-in via LLM_PROVIDER on the machine that sets it, exactly like CV generation's
CODEX_CV_ENABLED is off unless an operator turns it on.

TASK-106 adds job grounding on top: `suggest_questions()` and the `job=` kwarg on `analyze_answer()`
use a JobLead's linked JobEvaluation (main_gaps/missing_skills) and source text to make practice
questions and feedback reference what the app already knows about the role, instead of every session
being generic.
"""

from __future__ import annotations

from dataclasses import dataclass
from glob import glob
import json
import os
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GERMAN_STRUCTURE_WORDS = {"zuerst", "dann", "anschliessend", "schliesslich", "am ende", "zum beispiel"}
ENGLISH_STRUCTURE_WORDS = {"first", "then", "next", "finally", "for example", "as a result"}
GERMAN_HEDGES = {"vielleicht", "ich glaube", "ein bisschen", "unsicher", "eventuell"}
ENGLISH_HEDGES = {"maybe", "i think", "kind of", "sort of", "probably", "not sure"}
ACTION_WORDS = {
    "built",
    "led",
    "improved",
    "organized",
    "delivered",
    "implemented",
    "analysed",
    "analyzed",
    "optimised",
    "optimized",
    "geleitet",
    "verbessert",
    "entwickelt",
    "umgesetzt",
    "analysiert",
    "organisiert",
}
OLLAMA_DEFAULT_MODEL = "llama3.1:8b"
OLLAMA_MANIFEST_ENV_VAR = "OLLAMA_MANIFESTS_DIR"
OLLAMA_MODEL_PREFERENCE = [
    "llama3.1:8b",
    "llama3.2:latest",
    "llama3.3:latest",
    "gemma3:12b",
    "gemma3:4b",
    "llama3:8b",
    "gpt-oss:20b",
    "mistral-large:latest",
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "deepseek-coder-v2:16b",
    "qwen3-coder:latest",
    "qwen2.5-coder:32b",
]
NON_CHAT_OLLAMA_MODELS = {"nomic-embed-text:latest"}


@dataclass
class AnalysisResult:
    clarity: int
    structure: int
    confidence: int
    overall: int
    feedback: list[str]
    stronger_answer: str
    evaluator: str
    model: str | None
    fallback_used: bool


@dataclass
class QuestionSuggestions:
    """TASK-106: suggested practice questions, optionally grounded in a job's evaluation."""
    questions: list[str]
    grounded: bool  # True once the questions were derived from a real evaluation's gaps
    notice: str  # non-empty only when a linked job has no evaluation yet (AC3)
    evaluator: str
    model: str | None
    fallback_used: bool


@dataclass
class LLMConfig:
    provider: str
    model: str
    base_url: str
    strict: bool
    timeout_seconds: float


def analyze_answer(question: str, answer_text: str, language: str, *, job=None) -> AnalysisResult:
    config = _load_llm_config()

    if config.provider == "heuristic":
        result = _analyze_answer_with_heuristics(answer_text, language)
    else:
        try:
            result = _analyze_answer_with_local_llm(
                question=question,
                answer_text=answer_text,
                language=language,
                config=config,
            )
        except Exception:
            if config.strict:
                raise
            result = _analyze_answer_with_heuristics(answer_text, language)
            result.evaluator = config.provider
            result.model = config.model or None
            result.fallback_used = True

    # TASK-106 AC2: a job-linked session gets one extra, honest template line grounded in that
    # job's evaluation gaps -- not routed through the LLM, so it never invents a claim about the
    # job. No evaluation on the job means no line, same silent no-op as an unlinked session.
    grounding_line = _grounding_feedback_line(job.evaluations.first() if job else None, language)
    if grounding_line:
        result.feedback = [*result.feedback, grounding_line]
    return result


def _analyze_answer_with_heuristics(answer_text: str, language: str) -> AnalysisResult:
    normalized = " ".join(answer_text.strip().split())
    lower = normalized.lower()
    words = [word.strip(".,!?;:") for word in lower.split()]
    sentence_count = max(1, normalized.count(".") + normalized.count("!") + normalized.count("?"))
    word_count = len(words)
    avg_sentence_len = word_count / sentence_count if sentence_count else word_count

    structure_words = GERMAN_STRUCTURE_WORDS if language == "de" else ENGLISH_STRUCTURE_WORDS
    hedges = GERMAN_HEDGES if language == "de" else ENGLISH_HEDGES

    clarity = 62
    if 45 <= word_count <= 180:
        clarity += 10
    if 10 <= avg_sentence_len <= 24:
        clarity += 8
    if any(hedge in lower for hedge in hedges):
        clarity -= 6
    if word_count < 35:
        clarity -= 12

    structure = 58
    if sentence_count >= 3:
        structure += 8
    if any(token in lower for token in structure_words):
        structure += 14
    if any(token in lower for token in {"result", "impact", "ergebnis", "wirkung"}):
        structure += 8

    confidence = 60
    if any(token in lower for token in ACTION_WORDS):
        confidence += 12
    if any(hedge in lower for hedge in hedges):
        confidence -= 14
    if "i " in lower or " ich " in f" {lower} ":
        confidence += 6

    clarity = _clamp_score(clarity)
    structure = _clamp_score(structure)
    confidence = _clamp_score(confidence)
    overall = round((clarity + structure + confidence) / 3)

    feedback = _build_feedback(language, clarity, structure, confidence, word_count)
    stronger_answer = _rewrite_answer(normalized, language)

    return AnalysisResult(
        clarity=clarity,
        structure=structure,
        confidence=confidence,
        overall=overall,
        feedback=feedback,
        stronger_answer=stronger_answer,
        evaluator="heuristic",
        model=None,
        fallback_used=False,
    )


def _analyze_answer_with_local_llm(
    *,
    question: str,
    answer_text: str,
    language: str,
    config: LLMConfig,
) -> AnalysisResult:
    prompt = _build_evaluation_prompt(question=question, answer_text=answer_text, language=language)

    if config.provider == "ollama":
        payload = {
            "model": config.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        response_body = _post_json(
            f"{config.base_url.rstrip('/')}/api/generate",
            payload,
            timeout_seconds=config.timeout_seconds,
        )
        raw_content = response_body.get("response", "")
    elif config.provider == "ollama-windows":
        payload = {
            "model": config.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        response_body = _post_json_via_windows_curl(
            f"{config.base_url.rstrip('/')}/api/generate",
            payload,
            timeout_seconds=config.timeout_seconds,
        )
        raw_content = response_body.get("response", "")
    elif config.provider == "openai-compatible":
        payload = {
            "model": config.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an interview answer evaluator. "
                        "Return only valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }
        response_body = _post_json(
            f"{config.base_url.rstrip('/')}/v1/chat/completions",
            payload,
            timeout_seconds=config.timeout_seconds,
        )
        raw_content = response_body["choices"][0]["message"]["content"]
    else:
        raise RuntimeError(f"Unsupported LLM provider: {config.provider}")

    llm_payload = json.loads(raw_content)
    clarity = _clamp_score(int(llm_payload["clarity"]))
    structure = _clamp_score(int(llm_payload["structure"]))
    confidence = _clamp_score(int(llm_payload["confidence"]))
    overall = round((clarity + structure + confidence) / 3)

    feedback = [str(item).strip() for item in llm_payload["feedback"]][:4]
    stronger_answer = str(llm_payload["stronger_answer"]).strip()

    if not feedback or not stronger_answer:
        raise RuntimeError("LLM response was missing required interview analysis fields.")

    return AnalysisResult(
        clarity=clarity,
        structure=structure,
        confidence=confidence,
        overall=overall,
        feedback=feedback,
        stronger_answer=stronger_answer,
        evaluator=config.provider,
        model=config.model,
        fallback_used=False,
    )


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _build_feedback(
    language: str,
    clarity: int,
    structure: int,
    confidence: int,
    word_count: int,
) -> list[str]:
    if language == "de":
        notes = []
        notes.append(
            "Mach deine Antwort konkreter und nenne ein klares Beispiel."
            if clarity < 70
            else "Deine Antwort ist gut verständlich und ausreichend präzise."
        )
        notes.append(
            "Nutze eine klarere Reihenfolge wie Ausgangslage, Aktion und Ergebnis."
            if structure < 70
            else "Die Antwort hat bereits eine nachvollziehbare Struktur."
        )
        notes.append(
            "Sprich direkter über deinen Beitrag und vermeide Weichmacher."
            if confidence < 70
            else "Dein Ton wirkt überzeugend und eigenverantwortlich."
        )
        if word_count < 50:
            notes.append("Die Antwort ist für ein Interview etwas kurz. Füge mehr Substanz hinzu.")
        return notes

    notes = []
    notes.append(
        "Make the answer more concrete and anchor it in one clear example."
        if clarity < 70
        else "Your answer is easy to follow and reasonably precise."
    )
    notes.append(
        "Use a clearer flow such as situation, action, and result."
        if structure < 70
        else "Your answer already has a recognizable structure."
    )
    notes.append(
        "Own the result more directly and remove hedging language."
        if confidence < 70
        else "Your tone sounds direct and credible."
    )
    if word_count < 50:
        notes.append("The answer is a bit short for an interview. Add more substance and outcome.")
    return notes


def _rewrite_answer(answer_text: str, language: str) -> str:
    starter = "Kurz und stärker formuliert: " if language == "de" else "Stronger version: "
    if language == "de":
        return (
            f"{starter}Ich habe die Situation strukturiert analysiert, eine klare Lösung umgesetzt "
            f"und das Ergebnis messbar verbessert. {answer_text}"
        )
    return (
        f"{starter}I analyzed the situation, took clear ownership, implemented a concrete solution, "
        f"and improved the outcome in a measurable way. {answer_text}"
    )


# --- TASK-106: job-grounded question generation -------------------------------------------------


def suggest_questions(job, language: str) -> QuestionSuggestions:
    """Suggested practice questions for `language`, grounded in `job`'s evaluation when possible.

    Three floors, checked in order: no job linked -> generic pool; a linked job with no evaluation
    yet -> generic pool plus a visible notice (AC3); a linked job with an evaluation -> questions
    templated from its gap list (AC1/AC4), enhanced by a local LLM when one is configured, with the
    same fallback-unless-strict shape as analyze_answer (AC4's note).
    """
    if job is None:
        return QuestionSuggestions(
            questions=_generic_questions(language), grounded=False, notice="",
            evaluator="heuristic", model=None, fallback_used=False,
        )

    evaluation = job.evaluations.first()
    if evaluation is None:
        return QuestionSuggestions(
            questions=_generic_questions(language), grounded=False, notice=_no_evaluation_notice(language),
            evaluator="heuristic", model=None, fallback_used=False,
        )

    heuristic_questions = _grounded_questions_heuristic(job, evaluation, language)
    config = _load_llm_config()

    if config.provider == "heuristic":
        return QuestionSuggestions(
            questions=heuristic_questions, grounded=True, notice="",
            evaluator="heuristic", model=None, fallback_used=False,
        )

    try:
        llm_questions = _grounded_questions_with_local_llm(
            job=job, evaluation=evaluation, language=language, config=config,
        )
        return QuestionSuggestions(
            questions=llm_questions, grounded=True, notice="",
            evaluator=config.provider, model=config.model, fallback_used=False,
        )
    except Exception:
        if config.strict:
            raise
        return QuestionSuggestions(
            questions=heuristic_questions, grounded=True, notice="",
            evaluator=config.provider, model=config.model or None, fallback_used=True,
        )


def _gap_terms(evaluation) -> list[str]:
    """Ordered, deduped gap terms: missing_skills first (short, e.g. "Kubernetes"), then
    main_gaps (fuller sentences, e.g. "Deep Kubernetes/Terraform/on-call expectations") -- the two
    JobEvaluation fields the task names as "gaps/weak skills". required_skills is deliberately left
    out here: it lists what the role wants, not where this candidate is short.
    """
    terms: list[str] = []
    for value in list(evaluation.missing_skills or []) + list(evaluation.main_gaps or []):
        term = str(value).strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def _grounding_feedback_line(evaluation, language: str) -> str | None:
    if evaluation is None:
        return None
    terms = _gap_terms(evaluation)
    if not terms:
        return None
    listed = ", ".join(terms[:3])
    if language == "de":
        return (
            f"Für diese Rolle zählt besonders: {listed}. Verankere deine Antwort, wo es passt, "
            "an einem konkreten Beispiel dazu."
        )
    return (
        f"This role weighs {listed} heavily -- ground your answer in a concrete example touching "
        "one of these when it fits."
    )


def _generic_questions(language: str) -> list[str]:
    if language == "de":
        return [
            "Erzählen Sie mir von einer Situation, in der Sie unter Zeitdruck ein schwieriges Problem gelöst haben.",
            "Beschreiben Sie ein Projekt, auf das Sie stolz sind, und Ihren konkreten Beitrag dazu.",
            "Erzählen Sie von einer Meinungsverschiedenheit mit einem Kollegen und wie Sie sie gelöst haben.",
            "Wie priorisieren Sie, wenn mehrere Aufgaben gleichzeitig anstehen?",
            "Erzählen Sie von einer Situation, in der Sie sich schnell in ein neues Thema einarbeiten mussten.",
        ]
    return [
        "Tell me about a time you solved a difficult problem under a tight deadline.",
        "Describe a project you're proud of and your specific contribution.",
        "Tell me about a disagreement with a colleague and how you resolved it.",
        "Walk me through how you prioritize when multiple tasks compete for your time.",
        "Describe a time you had to learn something new quickly.",
    ]


def _no_evaluation_notice(language: str) -> str:
    if language == "de":
        return "Für diesen Job liegt noch keine Bewertung vor -- hier sind allgemeine Übungsfragen."
    return "This job has no evaluation yet -- showing generic practice questions instead."


def _grounded_questions_heuristic(job, evaluation, language: str) -> list[str]:
    title = job.title or ("diese Rolle" if language == "de" else "this role")
    company = job.company or ("das Unternehmen" if language == "de" else "the company")
    terms = _gap_terms(evaluation)

    if language == "de":
        opener = f"Was an Ihrem Hintergrund macht Sie zu einer starken Besetzung für {title} bei {company}?"
        gap_templates = [
            'Die Bewertung nennt "{term}" als Lücke -- erzählen Sie von einem Projekt, das diese '
            "Lücke schliesst, oder wie Sie sich schnell einarbeiten würden.",
            "Erzählen Sie mir von Ihrer praktischen Erfahrung mit {term}.",
        ]
    else:
        opener = f"What in your background makes you a strong fit for {title} at {company}?"
        gap_templates = [
            'The evaluation flagged "{term}" as a gap -- tell me about a project that closes that '
            "gap, or how you would ramp up quickly.",
            "Walk me through your hands-on experience with {term}.",
        ]

    questions = [opener]
    for index, term in enumerate(terms[:4]):
        questions.append(gap_templates[index % len(gap_templates)].format(term=term))
    return questions


def _build_question_prompt(*, job, evaluation, language: str) -> str:
    gap_terms = _gap_terms(evaluation)
    description = (job.source_text or "").strip()[:2000]
    return (
        "Generate interview practice questions for a DACH-focused interview coach.\n"
        f"Language: {language}\n"
        f"Job title: {job.title or '(unknown)'}\n"
        f"Company: {job.company or '(unknown)'}\n"
        f"Job description or source text: {description or '(not provided)'}\n"
        f"Evaluation gaps / weak skills to probe: {', '.join(gap_terms) or '(none)'}\n\n"
        "Return 4 to 6 realistic interview questions, in the given language, that specifically "
        "probe the listed gaps and reference the job description. Return only valid JSON with this "
        'exact shape: {"questions": ["question 1", "question 2", "question 3"]}'
    )


def _grounded_questions_with_local_llm(*, job, evaluation, language: str, config: LLMConfig) -> list[str]:
    prompt = _build_question_prompt(job=job, evaluation=evaluation, language=language)

    if config.provider == "ollama":
        payload = {"model": config.model, "prompt": prompt, "stream": False, "format": "json"}
        response_body = _post_json(
            f"{config.base_url.rstrip('/')}/api/generate", payload, timeout_seconds=config.timeout_seconds,
        )
        raw_content = response_body.get("response", "")
    elif config.provider == "ollama-windows":
        payload = {"model": config.model, "prompt": prompt, "stream": False, "format": "json"}
        response_body = _post_json_via_windows_curl(
            f"{config.base_url.rstrip('/')}/api/generate", payload, timeout_seconds=config.timeout_seconds,
        )
        raw_content = response_body.get("response", "")
    elif config.provider == "openai-compatible":
        payload = {
            "model": config.model,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an interview-question generator for a DACH-focused interview coach. "
                        "Return only valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        response_body = _post_json(
            f"{config.base_url.rstrip('/')}/v1/chat/completions", payload, timeout_seconds=config.timeout_seconds,
        )
        raw_content = response_body["choices"][0]["message"]["content"]
    else:
        raise RuntimeError(f"Unsupported LLM provider: {config.provider}")

    llm_payload = json.loads(raw_content)
    questions = [str(item).strip() for item in llm_payload["questions"] if str(item).strip()][:6]
    if not questions:
        raise RuntimeError("LLM response was missing required interview questions.")
    return questions


def _load_llm_config() -> LLMConfig:
    provider = os.getenv("LLM_PROVIDER", "heuristic").strip().lower()
    strict = os.getenv("LLM_STRICT", "false").strip().lower() == "true"
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))

    if provider == "ollama":
        return LLMConfig(
            provider="ollama",
            model=_resolve_ollama_model(os.getenv("LLM_MODEL")),
            base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434"),
            strict=strict,
            timeout_seconds=timeout_seconds,
        )

    if provider in {"ollama-windows", "ollama_windows"}:
        return LLMConfig(
            provider="ollama-windows",
            model=_resolve_ollama_model(os.getenv("LLM_MODEL")),
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
            strict=strict,
            timeout_seconds=timeout_seconds,
        )

    if provider in {"openai-compatible", "openai_compatible"}:
        return LLMConfig(
            provider="openai-compatible",
            model=os.getenv("LLM_MODEL", "local-model"),
            base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234"),
            strict=strict,
            timeout_seconds=timeout_seconds,
        )

    return LLMConfig(
        provider="heuristic",
        model="",
        base_url="",
        strict=False,
        timeout_seconds=timeout_seconds,
    )


def _build_evaluation_prompt(*, question: str, answer_text: str, language: str) -> str:
    return (
        "Evaluate this interview answer for a DACH-focused interview coach.\n"
        f"Language: {language}\n"
        f"Interview question: {question or '(not provided)'}\n"
        f"Candidate answer: {answer_text}\n\n"
        "Score the answer from 0 to 100 on these dimensions:\n"
        "- clarity: understandable, concise, concrete\n"
        "- structure: logical flow, context-action-result\n"
        "- confidence: ownership, directness, specificity\n\n"
        "Return only valid JSON with this exact shape:\n"
        '{'
        '"clarity": 0, '
        '"structure": 0, '
        '"confidence": 0, '
        '"feedback": ["short point 1", "short point 2", "short point 3"], '
        '"stronger_answer": "improved interview answer in the same language"'
        '}'
    )


def _post_json(url: str, payload: dict, timeout_seconds: float) -> dict:
    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local LLM request failed with HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach local LLM service at {url}.") from exc


def _post_json_via_windows_curl(url: str, payload: dict, timeout_seconds: float) -> dict:
    curl_path = os.getenv("WINDOWS_CURL_PATH", "/mnt/c/Windows/System32/curl.exe")
    body = json.dumps(payload)

    try:
        result = subprocess.run(
            [
                curl_path,
                "-sS",
                "--max-time",
                str(int(timeout_seconds)),
                "-H",
                "Content-Type: application/json",
                "-d",
                "@-",
                url,
            ],
            input=body,
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Windows curl binary was not found at {curl_path}. Set WINDOWS_CURL_PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip()
        raise RuntimeError(
            f"Windows-side Ollama request failed via curl.exe: {details or 'unknown error'}"
        ) from exc

    return json.loads(result.stdout)


def _resolve_ollama_model(configured_model: str | None) -> str:
    normalized = (configured_model or "").strip()
    if normalized and normalized.lower() != "auto":
        return normalized

    installed_models = _list_installed_ollama_models()
    return _pick_preferred_ollama_model(installed_models) or OLLAMA_DEFAULT_MODEL


def _pick_preferred_ollama_model(installed_models: list[str]) -> str | None:
    installed_lookup = set(installed_models)

    for model in OLLAMA_MODEL_PREFERENCE:
        if model in installed_lookup:
            return model

    chat_capable_models = sorted(model for model in installed_models if model not in NON_CHAT_OLLAMA_MODELS)
    if chat_capable_models:
        return chat_capable_models[0]

    return None


def _list_installed_ollama_models() -> list[str]:
    models: set[str] = set()

    for root in _candidate_ollama_manifest_roots():
        if not os.path.isdir(root):
            continue

        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                model_id = _manifest_path_to_model_id(root, os.path.join(current_root, filename))
                if model_id:
                    models.add(model_id)

    return sorted(models)


def _candidate_ollama_manifest_roots() -> list[str]:
    candidates = []
    configured_root = os.getenv(OLLAMA_MANIFEST_ENV_VAR, "").strip()
    if configured_root:
        candidates.append(configured_root)

    candidates.append(os.path.expanduser("~/.ollama/models/manifests/registry.ollama.ai"))
    candidates.extend(glob("/mnt/c/Users/*/.ollama/models/manifests/registry.ollama.ai"))

    deduped_candidates = []
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if normalized not in deduped_candidates:
            deduped_candidates.append(normalized)

    return deduped_candidates


def _manifest_path_to_model_id(root: str, manifest_path: str) -> str | None:
    relative_path = os.path.relpath(manifest_path, root)
    parts = relative_path.split(os.sep)
    if len(parts) < 3:
        return None

    namespace = parts[0]
    model_name = "/".join(parts[1:-1])
    tag = parts[-1]
    if not model_name or not tag:
        return None

    if namespace == "library":
        return f"{model_name}:{tag}"

    return f"{namespace}/{model_name}:{tag}"


def _detect_windows_ollama_base_url() -> str:
    host_ip = _read_wsl_host_ip()
    if host_ip:
        return f"http://{host_ip}:11434"

    return "http://127.0.0.1:11434"


def _read_wsl_host_ip() -> str | None:
    override = os.getenv("WSL_HOST_IP", "").strip()
    if override:
        return override

    resolv_conf = "/etc/resolv.conf"
    if not os.path.isfile(resolv_conf):
        return None

    try:
        with open(resolv_conf, encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("nameserver "):
                    continue
                _, value = line.split(maxsplit=1)
                return value.strip()
    except OSError:
        return None

    return None
