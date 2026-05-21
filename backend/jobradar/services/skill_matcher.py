import re

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


def smart_skill_status(skill):
    n=norm(skill)
    if not n: return 'unknown'
    for canonical, aliases in PROFILE_SKILL_GROUPS.items():
        if any(norm(a) == n or norm(a) in n or n in norm(a) for a in aliases + [canonical]):
            return 'match'
    for canonical, aliases in WEAKER_FIT.items():
        if any(norm(a) == n or norm(a) in n or n in norm(a) for a in aliases + [canonical]):
            return 'weak'
    return 'unknown'
