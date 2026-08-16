"""TASK-104: the evaluator ported from ai-interview-coach-dach, plus the practice endpoints.

Ported almost verbatim from the coach's tests/test_analysis.py (see
jobradar.services.interview_coach for the module-level note on the one dropped piece: the coach's
private .env loader, since config.settings already loads .env into os.environ for this whole
process before any test runs). isolate_llm_env no longer needs to patch ENV_FILE_CANDIDATES because
that mechanism does not exist here.

TASK-106 adds the job-grounding tests at the bottom: suggest_questions() and the job= kwarg on
analyze_answer().
"""
from io import StringIO

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobEvaluation, JobLead, PracticeSession
from jobradar.services.interview_coach import (
    _detect_windows_ollama_base_url,
    _list_installed_ollama_models,
    _load_llm_config,
    analyze_answer,
    suggest_questions,
)


@pytest.fixture(autouse=True)
def isolate_llm_env(monkeypatch):
    for key in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_BASE_URL",
        "LLM_STRICT",
        "LLM_TIMEOUT_SECONDS",
        "OLLAMA_MANIFESTS_DIR",
        "WSL_HOST_IP",
    ):
        monkeypatch.delenv(key, raising=False)


# --- Ported evaluator tests (AC1) --------------------------------------------------------------

def test_analyze_answer_returns_scores_and_feedback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")

    result = analyze_answer(
        "Tell me about a time you improved a process.",
        (
            "I improved our onboarding process by mapping the drop-off points, "
            "coordinating a simpler handoff with product and design, and reducing "
            "time to first value for customers."
        ),
        "en",
    )

    assert 0 <= result.clarity <= 100
    assert 0 <= result.structure <= 100
    assert 0 <= result.confidence <= 100
    assert result.overall == round(
        (result.clarity + result.structure + result.confidence) / 3
    )
    assert result.feedback
    assert result.stronger_answer.startswith("Stronger version:")


def test_analyze_answer_german_language_uses_german_feedback_and_rewrite():
    result = analyze_answer(
        "Erzähl mir von einer Herausforderung.",
        "Ich habe vielleicht ein bisschen geholfen, bin mir aber nicht sicher.",
        "de",
    )

    assert result.stronger_answer.startswith("Kurz und stärker formuliert:")
    assert any("Antwort" in note for note in result.feedback)


def test_load_llm_config_defaults_to_heuristic_with_nothing_configured():
    config = _load_llm_config()
    assert config.provider == "heuristic"
    assert config.strict is False


def test_load_llm_config_autodetects_an_installed_ollama_model(tmp_path, monkeypatch):
    manifest_root = tmp_path / "registry.ollama.ai"
    llama_manifest = manifest_root / "library" / "llama3.1" / "8b"
    gemma_manifest = manifest_root / "library" / "gemma3" / "12b"
    llama_manifest.parent.mkdir(parents=True)
    gemma_manifest.parent.mkdir(parents=True)
    llama_manifest.write_text("{}", encoding="utf-8")
    gemma_manifest.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_MANIFESTS_DIR", str(manifest_root))

    config = _load_llm_config()

    assert config.provider == "ollama"
    assert config.model == "llama3.1:8b"


def test_list_installed_ollama_models_includes_custom_namespace(tmp_path, monkeypatch):
    manifest_root = tmp_path / "registry.ollama.ai"
    deepseek_manifest = manifest_root / "nezahatkorkmaz" / "deepseek-v3" / "latest"
    deepseek_manifest.parent.mkdir(parents=True)
    deepseek_manifest.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("OLLAMA_MANIFESTS_DIR", str(manifest_root))

    models = _list_installed_ollama_models()

    assert "nezahatkorkmaz/deepseek-v3:latest" in models


def test_detect_windows_ollama_base_url_uses_wsl_host_ip(monkeypatch):
    monkeypatch.setattr("jobradar.services.interview_coach.os.path.isfile", lambda path: path == "/etc/resolv.conf")
    monkeypatch.setattr(
        "builtins.open",
        lambda path, encoding="utf-8": StringIO("nameserver 10.255.255.254\n"),
    )

    assert _detect_windows_ollama_base_url() == "http://10.255.255.254:11434"


# AC2 -- an unreachable configured model falls back to heuristics unless LLM_STRICT is set.

def test_unreachable_local_llm_falls_back_to_heuristics_by_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1")  # nothing listens here

    result = analyze_answer("Question?", "A reasonably long practice answer for the heuristic path.", "en")

    assert result.fallback_used is True
    assert result.evaluator == "openai-compatible"
    assert 0 <= result.clarity <= 100


def test_unreachable_local_llm_raises_when_strict(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("LLM_STRICT", "true")

    with pytest.raises(Exception):
        analyze_answer("Question?", "A reasonably long practice answer for the strict path.", "en")


# --- Practice endpoints (AC3/AC4) ---------------------------------------------------------------

VALID_ANSWER = (
    "I led the migration by mapping dependencies first, then coordinating a phased rollout with "
    "the platform team, and finally verifying the result with the on-call dashboard."
)


@pytest.fixture
def user(db):
    return User.objects.create_user("coach-user", password="pw")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("coach-other", password="pw")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    c.user = user
    return c


def test_evaluate_creates_a_practice_session_scoped_to_the_user(client, user):
    r = client.post(
        "/api/practice/evaluate/",
        {"question": "Tell me about a challenge.", "answer_text": VALID_ANSWER, "language": "en"},
        format="json",
    )

    assert r.status_code == 201, r.data
    assert r.data["language"] == "en"
    assert 0 <= r.data["clarity_score"] <= 100
    assert r.data["evaluator"] == "heuristic"
    assert PracticeSession.objects.filter(user=user).count() == 1


def test_evaluate_rejects_a_short_answer(client):
    r = client.post("/api/practice/evaluate/", {"answer_text": "too short", "language": "en"}, format="json")
    assert r.status_code == 400


def test_evaluate_rejects_an_unsupported_language(client):
    r = client.post("/api/practice/evaluate/", {"answer_text": VALID_ANSWER, "language": "fr"}, format="json")
    assert r.status_code == 400


def test_evaluate_links_a_job_the_user_can_access(client, user):
    job = JobLead.objects.create(company="Acme", title="Engineer", created_by=user)

    r = client.post(
        "/api/practice/evaluate/",
        {"answer_text": VALID_ANSWER, "language": "en", "job": job.id},
        format="json",
    )

    assert r.status_code == 201, r.data
    assert r.data["job"] == job.id
    assert r.data["job_company"] == "Acme"


def test_evaluate_rejects_a_job_the_user_cannot_access(client, other_user):
    other_job = JobLead.objects.create(company="Other Co", title="Role", created_by=other_user)

    r = client.post(
        "/api/practice/evaluate/",
        {"answer_text": VALID_ANSWER, "language": "en", "job": other_job.id},
        format="json",
    )

    assert r.status_code == 400


def test_evaluate_requires_authentication(db):
    r = APIClient().post("/api/practice/evaluate/", {"answer_text": VALID_ANSWER, "language": "en"}, format="json")
    assert r.status_code in (401, 403)


def test_history_lists_only_the_requesting_users_sessions_newest_first(client, user, other_user):
    older = PracticeSession.objects.create(
        user=user, question="Q1", answer_text=VALID_ANSWER, language="en",
        clarity_score=60, structure_score=60, confidence_score=60, overall_score=60,
        feedback=["ok"], stronger_answer="better",
    )
    newer = PracticeSession.objects.create(
        user=user, question="Q2", answer_text=VALID_ANSWER, language="en",
        clarity_score=70, structure_score=70, confidence_score=70, overall_score=70,
        feedback=["ok"], stronger_answer="better",
    )
    PracticeSession.objects.create(
        user=other_user, question="Not mine", answer_text=VALID_ANSWER, language="en",
        clarity_score=50, structure_score=50, confidence_score=50, overall_score=50,
        feedback=["ok"], stronger_answer="better",
    )

    r = client.get("/api/practice/history/")

    assert r.status_code == 200
    assert [row["id"] for row in r.data] == [newer.id, older.id]


# AC5 -- practice sessions ride the export and account-deletion paths.

def test_practice_session_is_included_in_the_user_data_export(client, user):
    PracticeSession.objects.create(
        user=user, question="Exported question", answer_text=VALID_ANSWER, language="en",
        clarity_score=60, structure_score=60, confidence_score=60, overall_score=60,
        feedback=["ok"], stronger_answer="better",
    )

    r = client.get("/api/export/")

    assert r.status_code == 200
    assert r.data["data"]["practice_sessions"][0]["question"] == "Exported question"


def test_practice_session_is_deleted_with_the_account(client, user):
    PracticeSession.objects.create(
        user=user, question="Gone soon", answer_text=VALID_ANSWER, language="en",
        clarity_score=60, structure_score=60, confidence_score=60, overall_score=60,
        feedback=["ok"], stronger_answer="better",
    )
    user_id = user.id  # force_authenticate hands request.user the same instance; delete_account's
    # user.delete() clears this object's own .pk in place, so the id must be captured beforehand.

    r = client.delete("/api/auth/account/", {"password": "pw"}, format="json")

    assert r.status_code == 200, r.data
    assert not PracticeSession.objects.filter(user_id=user_id).exists()


# --- TASK-106 -- job-grounded questions and feedback ---------------------------------------------


@pytest.fixture
def job_with_gaps(user):
    job = JobLead.objects.create(
        company="CloudOps AG", title="Platform Reliability Engineer", created_by=user,
        raw_description="Platform reliability role with Kubernetes, Terraform, CI/CD, Linux, observability.",
    )
    JobEvaluation.objects.create(
        job=job, fit_score=63, priority="medium", recommendation="maybe",
        summary="Some overlap, but platform depth may be a stretch.",
        main_gaps=["Deep Kubernetes/Terraform/on-call expectations"],
        required_skills=["Kubernetes", "Terraform", "Linux", "CI/CD"],
        matched_skills=["Linux"],
        missing_skills=["Kubernetes", "Terraform"],
    )
    return job


@pytest.fixture
def job_without_evaluation(user):
    return JobLead.objects.create(company="NoEval Inc", title="Engineer", created_by=user)


# AC1/AC4 -- grounded questions, heuristic mode, both languages.

def test_suggest_questions_grounds_in_evaluation_gap_terms_english(job_with_gaps):
    result = suggest_questions(job_with_gaps, "en")

    assert result.grounded is True
    assert result.notice == ""
    assert result.evaluator == "heuristic"
    joined = " ".join(result.questions)
    assert "Kubernetes" in joined
    assert "Terraform" in joined


def test_suggest_questions_grounds_in_evaluation_gap_terms_german(job_with_gaps):
    result = suggest_questions(job_with_gaps, "de")

    assert result.grounded is True
    joined = " ".join(result.questions)
    assert "Kubernetes" in joined
    assert "Terraform" in joined
    # German wording, not the English templates, for a German session.
    assert any("Erfahrung" in q or "Lücke" in q for q in result.questions)


# AC3 -- a linked job with no evaluation degrades to generic questions plus a visible notice.

def test_suggest_questions_falls_back_to_generic_with_notice_when_job_has_no_evaluation(job_without_evaluation):
    result = suggest_questions(job_without_evaluation, "en")

    assert result.grounded is False
    assert result.notice != ""
    assert result.questions  # still usable, not empty and not an error


def test_suggest_questions_is_generic_with_no_job_linked_at_all():
    result = suggest_questions(None, "en")

    assert result.grounded is False
    assert result.notice == ""
    assert result.questions


# AC2 -- feedback differs for a job-linked session vs the same answer with no job linked.

def test_analyze_answer_feedback_differs_when_job_is_linked(job_with_gaps):
    unlinked = analyze_answer("Tell me about a challenge.", VALID_ANSWER, "en")
    linked = analyze_answer("Tell me about a challenge.", VALID_ANSWER, "en", job=job_with_gaps)

    assert linked.feedback != unlinked.feedback
    assert len(linked.feedback) == len(unlinked.feedback) + 1
    assert "Kubernetes" in linked.feedback[-1]


def test_analyze_answer_feedback_unchanged_when_linked_job_has_no_evaluation(job_without_evaluation):
    unlinked = analyze_answer("Tell me about a challenge.", VALID_ANSWER, "en")
    linked = analyze_answer("Tell me about a challenge.", VALID_ANSWER, "en", job=job_without_evaluation)

    assert linked.feedback == unlinked.feedback


# API surface for the above.

def test_practice_questions_endpoint_returns_grounded_questions_for_linked_job(client, job_with_gaps):
    r = client.get(f"/api/practice/questions/?job={job_with_gaps.id}&language=en")

    assert r.status_code == 200, r.data
    assert r.data["grounded"] is True
    assert r.data["notice"] == ""
    assert "Kubernetes" in " ".join(r.data["questions"])


def test_practice_questions_endpoint_notice_when_linked_job_has_no_evaluation(client, job_without_evaluation):
    r = client.get(f"/api/practice/questions/?job={job_without_evaluation.id}&language=en")

    assert r.status_code == 200, r.data
    assert r.data["grounded"] is False
    assert r.data["notice"] != ""


def test_practice_questions_endpoint_rejects_a_job_the_user_cannot_access(client, other_user):
    other_job = JobLead.objects.create(company="Other Co", title="Role", created_by=other_user)

    r = client.get(f"/api/practice/questions/?job={other_job.id}")

    assert r.status_code == 404


def test_practice_evaluate_feedback_includes_job_grounding_line(client, job_with_gaps):
    r = client.post(
        "/api/practice/evaluate/",
        {"answer_text": VALID_ANSWER, "language": "en", "job": job_with_gaps.id},
        format="json",
    )

    assert r.status_code == 201, r.data
    assert "Kubernetes" in " ".join(r.data["feedback"])
