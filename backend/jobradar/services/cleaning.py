import re

_COUNTRY_WORDS = r'(?:Austria|Österreich|Oesterreich|Germany|Deutschland|Switzerland|Schweiz|Suisse|Hungary|Greece|Netherlands|France|Spain|Italy|Portugal|Poland|Czechia|Czech Republic|Slovakia|Slovenia|Romania|Bulgaria|Belgium|Denmark|Sweden|Norway|Finland|Ireland|United Kingdom|UK|USA|United States)'
_COUNTRY_CODES = r'(?:AUT|AT|DEU|DE|CHE|CH|HUN|HU|GRC|GR|NLD|NL|FRA|FR|ESP|ES|ITA|IT|PRT|PT|POL|PL|CZE|CZ|SVK|SK|SVN|SI|ROU|RO|BGR|BG|BEL|BE|DNK|DK|SWE|SE|NOR|NO|FIN|FI|IRL|IE|GBR|GB|UK|USA|US)'
_KNOWN_CITIES = [
    ('Vienna', r'Vienna|Wien'), ('Berlin', r'Berlin'), ('Munich', r'Munich|München|Muenchen'),
    ('Hamburg', r'Hamburg'), ('Frankfurt', r'Frankfurt(?: am Main)?'), ('Cologne', r'Cologne|Köln|Koeln'),
    ('Stuttgart', r'Stuttgart'), ('Düsseldorf', r'Düsseldorf|Duesseldorf'), ('Graz', r'Graz'),
    ('Linz', r'Linz'), ('Salzburg', r'Salzburg'), ('Innsbruck', r'Innsbruck'), ('Klagenfurt', r'Klagenfurt'),
    ('Zurich', r'Zurich|Zürich|Zuerich'), ('Basel', r'Basel'), ('Bern', r'Bern'), ('Geneva', r'Geneva|Genève|Genf'),
    ('Budapest', r'Budapest'), ('Thessaloniki', r'Thessaloniki'), ('Athens', r'Athens'),
]

def clean_job_location(value):
    """Keep job locations concise for prompts/UI.

    Examples: "Vienna, AUT 1100" -> "Vienna", "AUT 1100 Wien" -> "Vienna".
    Preserves broad/remote labels when no specific city is visible.
    """
    text = re.sub(r'\s+', ' ', str(value or '')).strip(' ,;:-')
    if not text:
        return ''
    for canonical, pattern in _KNOWN_CITIES:
        if re.search(rf'\b(?:{pattern})\b', text, flags=re.I):
            return canonical
    text = re.sub(rf'\b{_COUNTRY_CODES}\b', ' ', text, flags=re.I)
    text = re.sub(rf'\b{_COUNTRY_WORDS}\b', ' ', text, flags=re.I)
    text = re.sub(r'\b\d{3,6}\b', ' ', text)
    text = re.sub(r'\b(?:postal\s*code|postcode|zip|plz)\b', ' ', text, flags=re.I)
    parts = [p.strip(' ,;:-') for p in re.split(r'[,;/|]+', text) if p.strip(' ,;:-')]
    if parts:
        text = parts[0]
    text = re.sub(r'\s+', ' ', text).strip(' ,;:-')
    return text or str(value or '').strip()
