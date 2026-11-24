"""TASK-409: a generated letter as plain text for an application form. Reads TeX, writes nothing, calls no model."""
import re

GREETING = re.compile(r'^[ \t]*(?:\\noindent\b\s*)?(?=(?:Sehr geehrt|Dear\b|Guten Tag\b|Hallo\b|Liebe|Hello\b|Hi\b))', re.MULTILINE)
CLOSING = re.compile(r'(?:freundliche[nm]?|viele|beste|herzliche[nm]?) Gr(?:ü|u|ue)(?:ß|ss)|regards|sincerely|faithfully|best wishes', re.IGNORECASE)
ACCENTS = {'"a': 'ä', '"o': 'ö', '"u': 'ü', '"A': 'Ä', '"O': 'Ö', '"U': 'Ü', "'e": 'é', '`e': 'è', "'a": 'á', '`a': 'à', '^e': 'ê', '~n': 'ñ'}
BREAK = '\0'


def plain_text(tex):
    """(text, complete). complete is False when no greeting or no closing was found; the text is then not cut there."""
    body = re.search(r'\\begin\{document\}(.*?)(?:\\end\{document\}|\Z)', tex.replace('\r\n', '\n'), re.DOTALL)
    body = re.sub(r'(?<!\\)%[^\n]*', '', body[1] if body else tex)
    start = GREETING.search(body)
    text = body[start.end():] if start else body
    text = re.sub(r'\\\\(?:\[[^\]]*\])?', BREAK, text)
    text = re.sub(r'\\(?:vspace|vskip)\*?\s*\{[^}]*\}|\\(?:par|bigskip|medskip|smallskip)\b|\\(?:begin|end)\{[^}]*\}(?:\{@?\{?[^\n]*\}[ \t]*(?=\n))?', '\n\n', text)
    text = re.sub(r'\\hspace\*?\s*\{[^}]*\}|\\(?:hfill|quad|qquad)\b|\\[,;: ]|(?<!\\)~', ' ', text)
    text = re.sub(r'\\item\b\s*(?:\[[^\]]*\])?', BREAK + '- ', text)
    text = re.sub(r'\\href\{[^{}]*\}', '', text)  # the link's own text follows in braces
    text = re.sub(r'\\(["\'`^~])\{?([A-Za-z])\}?', lambda m: ACCENTS.get(m[1] + m[2], m[2]), text)
    text = re.sub(r'\\ss\b\s*(?:\{\})?', 'ß', text)
    text = re.sub(r'\\glqq\b(?:\{\})?\s*', '„', text)
    text = re.sub(r'\\grqq\b(?:\{\})?', '“', text)
    text = re.sub(r'\\today\b(?:\{\})?', '', text)
    text = re.sub(r'\\([&%$#_{}])', lambda m: {'{': '\1', '}': '\2'}.get(m[1], m[1]), text)  # an escaped brace is text
    text = re.sub(r'\\[A-Za-z]+\*?\s*', '', text)  # formatting only: what it formats stays
    text = text.replace('{', '').replace('}', '').replace('\1', '{').replace('\2', '}')
    for tex_mark, mark in (('---', '—'), ('--', '–'), ('"`', '„'), ('"\'', '“'), ('``', '“'), ("''", '”'), ('`', '‘')):
        text = text.replace(tex_mark, mark)
    paragraphs = []
    for block in re.split(r'\n\s*\n', text):
        lines = [' '.join(line.split()) for line in block.split(BREAK)]
        block = '\n'.join(line for line in lines if line)
        if block:
            paragraphs.append(block)
    result = '\n\n'.join(paragraphs)
    return result, bool(start and CLOSING.search(result))
