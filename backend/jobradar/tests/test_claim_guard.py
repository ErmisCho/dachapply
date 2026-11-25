from jobradar.services.claim_guard import unsupported_claims as guard

EV = "Deutsch: B2, English (C1). Skills: Python, Django, C#, Databricks."


def test_unowned_certificate_flagged():
    assert any("goethe" in x for x in guard("Goethe-Zertifikat B2", "Deutsch B2"))


def test_certificate_present_in_evidence_not_flagged():
    assert guard("Goethe-Zertifikat B2", "Goethe-Zertifikat B2, Deutsch B2") == []


def test_language_level_not_in_evidence_flagged():
    assert guard("German C1 and English C1", EV) == ["language level: German C1"]


def test_language_level_phrasing_is_normalised():
    assert guard("B2 Deutsch; Englisch (C1)", EV) == []


def test_posting_tool_flagged_when_absent():
    got = guard("Skills: Python, Databricks, Snowflake", "Python", "We use Databricks and Snowflake")
    assert got == ["technology not in evidence: Databricks", "technology not in evidence: Snowflake"]


def test_posting_tool_present_lowercase_not_flagged():
    assert guard("Used Databricks daily", "databricks", "Databricks required") == []


def test_tex_escapes_match_plain_text():
    assert guard(r"\textbf{C\#} and Node\.js, R\&D", "C#, node.js", "C# Node.js") == []


def test_everything_supported_gives_empty_list():
    assert guard("Python, Django. Deutsch B2", EV, "Python Django Databricks") == []


def test_garbage_input_returns_empty_list():
    assert guard(None, 5, object()) == []
