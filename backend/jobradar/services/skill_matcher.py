import re
from functools import lru_cache

DISPLAY_NAMES = {
    'python': 'Python', 'python 3': 'Python', 'python3': 'Python',
    'django rest framework': 'DRF', 'drf': 'DRF',
    'postgres': 'PostgreSQL', 'postgresql': 'PostgreSQL',
    'mysql': 'MySQL', 'rest api': 'REST APIs', 'rest apis': 'REST APIs', 'api': 'REST APIs', 'apis': 'REST APIs',
    'elasticsearch': 'Elasticsearch/OpenSearch', 'opensearch': 'Elasticsearch/OpenSearch', 'open search': 'Elasticsearch/OpenSearch',
    'k8s': 'Kubernetes', 'kubernetes': 'Kubernetes',
    'microsoft azure': 'Azure', 'amazon web services': 'AWS',
    'retrieval augmented generation': 'RAG', 'retrieval augmented': 'RAG',
    'vector search': 'Semantic search', 'embeddings': 'Semantic search',
}

PROFILE_SKILL_GROUPS = {
    'python': ['python', 'python3', 'python 3'],
    'django': ['django', 'django rest framework', 'drf'],
    'fastapi': ['fastapi', 'fast api'],
    'rest apis': ['rest', 'rest api', 'rest apis', 'api', 'apis'],
    'java': ['java'],
    'sql': ['sql', 'postgresql', 'postgres', 'mysql', 'relational database', 'relational databases'],
    'postgresql': ['postgresql', 'postgres'],
    'mysql': ['mysql'],
    'docker': ['docker', 'container'],
    'linux': ['linux'],
    'kubernetes': ['kubernetes', 'k8s'],
    'aws': ['aws', 'amazon web services'],
    'azure': ['azure', 'microsoft azure'],
    'redis': ['redis'],
    'rabbitmq': ['rabbitmq', 'rabbit mq'],
    'elasticsearch': ['elasticsearch', 'elastic search', 'opensearch', 'open search'],
    'rag': ['rag', 'retrieval augmented generation', 'retrieval-augmented generation'],
    'semantic search': ['semantic search', 'vector search', 'embeddings'],
    'langchain': ['langchain', 'lang chain'],
    'langgraph': ['langgraph', 'lang graph'],
    'background processing': ['async', 'asynchronous', 'background processing', 'celery', 'workers', 'queues'],
    'finance': ['finance', 'fintech', 'banking'],
    'telecom': ['telecom', 'telecommunications'],
    'german': ['german', 'deutsch'],
    'english': ['english'],
}

WEAKER_FIT = {
    'react': ['react', 'reactjs', 'react.js'],
    'typescript': ['typescript', 'type script'],
    'terraform': ['terraform'],
    'spark': ['spark', 'apache spark'],
    'deep devops': ['sre', 'site reliability', 'devops'],
    'ml research': ['ml research', 'machine learning research', 'phd'],
}


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


# TASK-283: the alias tables are constants, so normalise them once. smart_skill_status used to
# re-normalise every alias for every skill of every board row -- 945k regex calls, ~75% of a
# 1.3 s /api/jobs/?board=1 on the owner's 111 jobs.
_PROFILE_NORMS = [[norm(a) for a in aliases + [canonical]] for canonical, aliases in PROFILE_SKILL_GROUPS.items()]
_WEAKER_NORMS = [[norm(a) for a in aliases + [canonical]] for canonical, aliases in WEAKER_FIT.items()]


@lru_cache(maxsize=4096)
def display_skill_name(skill):
    n=norm(skill)
    if n in DISPLAY_NAMES: return DISPLAY_NAMES[n]
    for key, val in DISPLAY_NAMES.items():
        if key in n: return val
    words=(skill or '').strip().replace('_',' ').replace('-', ' ')
    return ' '.join(w.capitalize() if w.islower() else w for w in words.split())[:32]


@lru_cache(maxsize=4096)
def smart_skill_status(skill):
    n=norm(skill)
    if not n: return 'unknown'
    for group in _PROFILE_NORMS:
        if any(a == n or a in n or n in a for a in group):
            return 'match'
    for group in _WEAKER_NORMS:
        if any(a == n or a in n or n in a for a in group):
            return 'weak'
    return 'unknown'
