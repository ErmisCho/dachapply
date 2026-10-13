"""TASK-283: smart_skill_status precomputes its alias norms and caches results. It must answer
exactly what the uncached, re-normalising version answered, for every alias it knows and for
inputs it does not."""
from jobradar.services import skill_matcher as m


def _reference_status(skill):
    n = m.norm(skill)
    if not n: return 'unknown'
    for table, verdict in ((m.PROFILE_SKILL_GROUPS, 'match'), (m.WEAKER_FIT, 'weak')):
        for canonical, aliases in table.items():
            if any(m.norm(a) == n or m.norm(a) in n or n in m.norm(a) for a in aliases + [canonical]):
                return verdict
    return 'unknown'


def test_cached_matcher_matches_the_reference_implementation():
    inputs = [None, '', '  ', 'C++', 'React.js', 'Senior Python 3 dev', 'k8s', 'Go', 'ab', 'Rust', 'PhD',
              'Amazon Web Services (AWS)', 'Cybersecurity experience']
    for table in (m.PROFILE_SKILL_GROUPS, m.WEAKER_FIT):
        for canonical, aliases in table.items():
            inputs += [canonical, canonical.upper(), *aliases]
    inputs += list(m.DISPLAY_NAMES)
    for skill in inputs * 2:  # second pass is served from the cache
        assert m.smart_skill_status(skill) == _reference_status(skill), skill
