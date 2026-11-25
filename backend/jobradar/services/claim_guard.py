"""Flag claims in generated CV/letter text that the candidate evidence does not support."""

import re
import unicodedata

_LANGS = {
    "english": "English", "englisch": "English", "german": "German", "deutsch": "German",
    "greek": "Greek", "griechisch": "Greek", "french": "French", "französisch": "French",
    "spanish": "Spanish", "spanisch": "Spanish", "italian": "Italian", "italienisch": "Italian",
    "russian": "Russian", "russisch": "Russian", "turkish": "Turkish", "türkisch": "Turkish",
}
_LEVEL = r"(?:[abc][12]|muttersprache|native(?: speaker)?)"
_LANG = "(?:" + "|".join(_LANGS) + ")"
_PAIRS = (
    re.compile(rf"\b({_LANG})\b\W{{0,4}}({_LEVEL})\b"),
    re.compile(rf"\b({_LEVEL})\s+({_LANG})\b"),
)
_CERT = re.compile(
    r"([\w.+#]{3,})[ -](?:zertifikat|certificate|certified|certification|zertifiziert)\b"
    r"(?:\s+[abc][12]\b)?"
)
_TOKEN = re.compile(r"\.?[A-Za-z][\w+#./]*[\w+#]|\b[A-Z]\b")
# Words that look like technologies but are not (shortcut: extend when a false positive shows up).
_STOP = {"ich", "sie", "wir", "we", "you", "und", "and", "the", "der", "die", "das", "eu", "it",
         "gmbh", "ag", "hr", "ceo", "cv", "pdf", "uk", "usa", "ok", "ba", "bsc", "msc", "phd",
         "z.b", "d.h", "e.g", "i.e", "etc", "ca", "ggf", "bzw"}


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\\([^A-Za-z\s])", r"\1", text)  # C\# -> C#, \& -> &, Node\.js -> Node.js
    text = re.sub(r"\\[A-Za-z]+\*?", "", text)  # \textbf{X} -> {X}
    return re.sub(r"[{}]", "", text)


def _pairs(text: str) -> set[tuple[str, str]]:
    found = set()
    for i, rx in enumerate(_PAIRS):
        for m in rx.finditer(text):
            lang, level = (m.group(1), m.group(2)) if i == 0 else (m.group(2), m.group(1))
            found.add((_LANGS[lang], "native" if level[0] in "mn" else level.upper()))
    return found


def _has(haystack: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?![\w+#])", haystack) is not None


def unsupported_claims(generated_text: str, evidence_text: str, posting_text: str = "") -> list[str]:
    """Sorted, de-duplicated descriptions of claims in generated_text absent from evidence_text."""
    try:
        gen_raw, ev_raw, post_raw = _clean(generated_text), _clean(evidence_text), _clean(posting_text)
        gen, ev = gen_raw.casefold(), ev_raw.casefold()
        out = set()
        for m in _CERT.finditer(gen):
            if not _has(ev, m.group(1)):
                out.add("certificate: " + m.group(0).strip())
        for lang, level in _pairs(gen) - _pairs(ev):
            out.add(f"language level: {lang} {level}")
        for tok in set(_TOKEN.findall(post_raw)):
            term = tok.casefold()
            if term in _STOP or len(term) < 2 or not (tok[0].isupper() or tok[0] == "."):
                continue
            strong = bool(re.search(r"[\d+#./]", tok)) or tok.isupper() or any(c.isupper() for c in tok[1:])
            # Plain capitalised words are mostly German nouns; trust them only inside a Tool, List.
            in_list = re.search(rf"(?:[,/]\s*{re.escape(tok)}\b|\b{re.escape(tok)}\s*[,/]\s*[A-Z])", gen_raw)
            if (strong or in_list) and _has(gen, term) and not _has(ev, term):
                out.add("technology not in evidence: " + tok)
        return sorted(out)
    except Exception:
        return []
