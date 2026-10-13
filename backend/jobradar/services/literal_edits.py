"""TASK-278: free-form literal CV edits applied without regenerating the document.

Two translators turn an instruction into (old, new) pairs -- a deterministic phrase parser and,
failing that, an installed local model -- and one gate decides whether the pairs may be applied.
Anything the gate refuses goes to full optimization; a wrong applied edit is worse than a slow one.

Gate rules (all must hold, for every pair, or the whole request is refused):
  1. each old is non-empty, differs from new, has no '...' wildcard line, and matches exactly once
     across the selected documents (cv_generator.match_exact_pair -- the OLD:/NEW: matcher,
     including its LaTeX-escape variant); "already applied" does not count as a match;
  2. no two pairs touch overlapping spans; the edited text is the source with only those spans
     spliced, and every byte outside them is checked identical to the source;
  3. no invented content: every word of the replacement that is not a word of the replaced text
     occurs in the instruction. A word is a run of Unicode letters/digits (`[^\\W_]+`) or a LaTeX
     command name (`\\textbf` -> `textbf`), compared case-insensitively after NFKC normalisation;
     escapes such as `\\&` carry no word. An accent macro (`M\\"unchen`) does not equal `München`,
     so such an edit is refused -- the safe direction;
  4. mixed requests are never claimed: the parser claims an instruction only when every non-blank
     line is an edit (or a bare "keep everything else unchanged") and an unquoted side holds no
     second clause (and/also/then/but, a sentence break); the model must answer literal=true; and,
     for both routes, every word of the instruction must be explained -- it is a word of some
     replaced text or replacement, or one of EDIT_WORDS (edit verbs, function words, field names
     such as "title" or "phone"). An unexplained word ("concise", "add", "translate") refuses
     the request: fail closed, because measured with gemma3:4b the model alone answered
     literal=true for 'replace "Hamburg" with "Berlin" and make the summary more concise'.
Compilation and page limits are checked afterwards, before anything is written
(cv_tasks._run_literal -> recompile_generated_package).
"""
import re
import tempfile
import time
import unicodedata
from pathlib import Path

from django.conf import settings

from jobradar.services.cv_generator import GenerationCancelled, available_model_options, match_exact_pair, run_structured_model


class NotLiteral(Exception):
    """The request is not (provably) a set of literal edits; the message is the reason shown in the report."""


_OPEN='"\u201c\u201e\u00ab\'\u2018\u201a'
_CLOSE='"\u201d\u201c\u00bb\'\u2019\u2018'
_FORMS=((r'(?:replace)',r'with'),(r'(?:change)',r'to'),('',r'->|\u2192'))
_BULLET=re.compile(r'^\s*(?:[-*\u2022]|\d+[.)])\s+')
_PLEASE=re.compile(r'^please\s+',re.IGNORECASE)
_GOAL=re.compile(r'^(?:be|sound|read|look|feel|make|more|less|something|shorter|longer|better|fit|match|reflect|focus|emphasi[sz]e|highlight|mention|include)\b',re.IGNORECASE)
# A '.' after a digit is a German date ('1. Oktober'), not the end of a sentence.
_CLAUSE=re.compile(r'\b(?:and|also|then|but|plus|und|auch)\b|(?<!\d)[.!?;]\s',re.IGNORECASE)
# TASK-278 follow-up: '... should say NEW rather than OLD' names the new text first.
_INVERTED=re.compile(r'^(?:.*?\s)?(?:say|says|read|reads|lauten|lautet)\s+(.+?)\s+(?:rather\s+than|instead\s+of|anstatt|statt)\s+(.+?)\s*[.!]?$',re.IGNORECASE|re.DOTALL)
_INVERTED_SEPARATOR=re.compile(r'\b(?:rather\s+than|instead\s+of|anstatt|statt)\b',re.IGNORECASE)
_KEEP_REST=re.compile(r"^(?:please\s+)?(?:(?:keep|leave)\s+(?:everything|all|the\s+rest)\s+else\s+(?:unchanged|as\s+is|the\s+same)|(?:do\s+not|don't)\s+change\s+anything\s+else)[.!]?$",re.IGNORECASE)


def _quoted(text):
    if len(text) >= 2 and text[0] in _OPEN and text[-1] in _CLOSE:
        return text[1:-1]
    return None


def _parse_segment(segment):
    """One edit from one segment, or None. Separators inside quotes are fine; unquoted text must
    contain its separator exactly once, otherwise the split is ambiguous and nothing is claimed."""
    segment=_PLEASE.sub('',_BULLET.sub('',segment).strip()).strip()
    inverted=_INVERTED.match(segment)
    if inverted and len(_INVERTED_SEPARATOR.findall(segment)) == 1:
        new,old=(part.strip() for part in inverted.groups())
        if any(';' in part or _CLAUSE.search(part) and _quoted(part) is None for part in (new,old)) or _quoted(new) is None and _GOAL.match(new):
            return None
        return (_quoted(old) if _quoted(old) is not None else old),(_quoted(new) if _quoted(new) is not None else new)
    for verb,separator in _FORMS:
        head=rf'^{verb}\s+' if verb else '^'
        # Lazy and greedy must agree: `replace 'a' with 'b' and 'c' with 'd'` splits two ways.
        quoted=[re.match(rf'{head}([{_OPEN}])(.+{lazy})([{_CLOSE}])\s*(?:{separator})\s*([{_OPEN}])(.+{lazy})([{_CLOSE}])\s*[.;!]?$',segment,re.IGNORECASE|re.DOTALL) for lazy in ('?','')]
        if quoted[0] or quoted[1]:
            parses={(match.group(2),match.group(5)) for match in quoted if match}
            if len(parses) == 1 and all(match for match in quoted):
                old,new=parses.pop()
                if not any(mark in old+new for mark in '"“”„'):
                    return old,new
            return None
        body=re.match(rf'{head}(.+)$',segment,re.IGNORECASE|re.DOTALL)
        if not body:
            continue
        parts=[part.strip() for part in re.split(rf'\s+(?:{separator})\s+' if verb else rf'\s*(?:{separator})\s*',body.group(1),flags=re.IGNORECASE)]
        # A half-quoted side ('"b" and make it shorter') or a ';' means more than one edit is here.
        if len(parts) != 2 or any(';' in part or (part[:1] in _OPEN or part[-1:] in _CLOSE or _CLAUSE.search(part)) and _quoted(part) is None for part in parts):
            continue
        old,new=parts
        old=_quoted(old) if _quoted(old) is not None else old
        new=_quoted(new) if _quoted(new) is not None else re.sub(r'[.!]$','',new)
        # Unquoted 'change Summary to be more concise' reads like an edit but is a request; an
        # unquoted replacement that opens like a description of a goal is never claimed.
        if old and new and not (_quoted(parts[1]) is None and _GOAL.match(new)):
            return old,new
    return None


def deterministic_edit_pairs(instructions):
    """Pairs for an instruction made only of `replace "X" with "Y"`, `change "X" to "Y"`,
    `X -> Y` / `X → Y` and `... should say Y rather than / instead of X` lines (quotes optional, keywords case-insensitive, several per message, one
    per line or separated by ';'). None as soon as any line is something else -- no partial claim."""
    pairs=[]
    for line in (instructions or '').replace('\r\n','\n').split('\n'):
        if not line.strip() or _KEEP_REST.match(line.strip()):
            continue
        parsed=_parse_segment(line)
        if parsed:
            pairs.append(parsed)
            continue
        segments=[_parse_segment(part) for part in line.split(';') if part.strip()]
        if len(segments) < 2 or not all(segments):
            return None
        pairs.extend(segments)
    return pairs or None


_WORD=re.compile(r'\\[A-Za-z@]+|[^\W_]+')
# Words an edit request may use without them being part of an edit. Deliberately closed: a word
# outside this list and outside every edit makes the request "more than literal" (gate rule 4).
EDIT_WORDS=frozenset('''
replace replaced change changed swap switch rename renamed update updated correct use set
with to by for from into instead of as is are am be should must read reads say says now new old
current currently the a an my me i it its this that these those one and or in on at please just
word words text name title role city location phone number mobile email e mail address header
line entry instead moved now keep everything else unchanged all rest same do not don t anything
ersetze ersetzen durch mit zu statt ändere ändern bitte die der das den dem mein meine meinen ist
soll sollte jetzt neu
rather than anstatt lauten lautet letter cv resume date datum lebenslauf anschreiben motivationsschreiben brief zeile
'''.split())


def words(text):
    return {word.lstrip('\\').casefold() for word in _WORD.findall(unicodedata.normalize('NFKC',text))}


def _outside_spans_identical(original, edited, spans):
    position=offset=0
    for start,end,replacement in spans:
        if original[position:start] != edited[offset:offset+start-position]:
            return False
        offset+=start-position
        if edited[offset:offset+len(replacement)] != replacement:
            return False
        offset+=len(replacement)
        position=end
    return original[position:] == edited[offset:]


def gate_literal_edits(documents, instructions, pairs):
    """Apply `pairs` to `documents` ({path: text}) only if every gate rule holds.

    Returns (updates, edits): updates is {path: new text} for changed documents, edits is the list
    of (replaced text, replacement) as applied. Raises NotLiteral otherwise -- never a partial set.
    """
    if not pairs:
        raise NotLiteral('no edits')
    allowed=words(instructions)
    spans={}
    edits=[]
    for old,new in pairs:
        if not old.strip() or old == new or any(line.strip() == '...' for line in old.split('\n')):
            raise NotLiteral('an edit was empty or unbounded')
        selected=match_exact_pair(documents,old,new)
        if selected is None or not selected[0]:
            raise NotLiteral(f'"{shorten(old)}" does not occur exactly once')
        path,start,end,replacement=selected
        replaced=documents[path][start:end]
        if replaced == replacement:
            raise NotLiteral('an edit changes nothing')
        invented=words(replacement)-words(replaced)-allowed
        if invented:
            raise NotLiteral(f'an edit adds words not in the request ({", ".join(sorted(invented)[:5])})')
        spans.setdefault(path,[]).append((start,end,replacement))
        edits.append((replaced,replacement))
    explained=set(EDIT_WORDS).union(*(words(old)|words(new) for old,new in pairs),*(words(old)|words(new) for old,new in edits))
    unexplained={word for word in allowed-explained if not (word.isdigit() and len(word) <= 2)}
    if unexplained:
        raise NotLiteral(f'the request asks for more than these edits ({", ".join(sorted(unexplained)[:5])})')
    updates={}
    for path,items in spans.items():
        items.sort()
        if any(later[0] < earlier[1] for earlier,later in zip(items,items[1:])):
            raise NotLiteral('two edits overlap')
        text=documents[path]
        for start,end,replacement in reversed(items):
            text=text[:start]+replacement+text[end:]
        if not _outside_spans_identical(documents[path],text,items):
            raise NotLiteral('text outside the edited spans changed')
        updates[path]=text
    return updates,edits


def shorten(text, limit=80):
    text=' '.join(text.split())
    return text if len(text) <= limit else text[:limit-1]+'\u2026'


def literal_report(updates, edits, route):
    return {'changed_files':[Path(path).name for path in updates],
            'main_changes':[f'{shorten(old)} -> {shorten(new)}' for old,new in edits]+[f'Route: {route}.'],
            'unsupported_requirements_not_claimed':[]}


def local_literal_model():
    """(provider, model) from settings.CODEX_CV_LITERAL_EDIT_MODEL ('ollama:<model>' or
    'lmstudio:<model>') when that model is installed; None disables the local-model route."""
    provider,_,model=(getattr(settings,'CODEX_CV_LITERAL_EDIT_MODEL','') or '').partition(':')
    if provider not in ('ollama','lmstudio') or not model:
        return None
    if not any(option['provider'] == provider and option['key'] == model for option in available_model_options()):
        return None
    return provider,model


EDIT_SCHEMA={
    'type':'object',
    'properties':{
        'literal':{'type':'boolean'},
        'edits':{'type':'array','items':{'type':'object','properties':{'old':{'type':'string'},'new':{'type':'string'}},'required':['old','new'],'additionalProperties':False}},
    },
    'required':['literal','edits'],
    'additionalProperties':False,
}

_PROMPT='''You translate a CV edit request into exact text replacements, or refuse.
Answer JSON: {"literal": true|false, "edits": [{"old": "...", "new": "..."}]}.

literal=true ONLY when the WHOLE request is replacing specific text with specific replacement text that the request itself spells out.
- "old" is copied character for character from the documents below (keep LaTeX such as \\& or \\textbf{...} exactly) and must occur exactly once; add a few neighbouring words if needed to make it unique.
- "new" is "old" with only the requested change. Never add, drop or reword anything else.
literal=false with edits=[] when ANY part of the request asks to rewrite, shorten, improve, rephrase, translate, reorder, add or remove content in general terms, change layout, or when the target text is ambiguous or not in the documents.

REQUEST:
<<<
{instructions}
>>>

DOCUMENTS:
{documents}'''


def translate_literal_edits(documents, instructions, provider, model, cancelled=None, timeout=None):
    """Ask the local model for {"literal", "edits"}; return the pairs, or raise NotLiteral when it
    refuses, errors, answers malformed JSON, or exceeds `timeout` seconds (user cancellation still
    raises GenerationCancelled)."""
    timeout=timeout if timeout is not None else getattr(settings,'CODEX_CV_LITERAL_EDIT_TIMEOUT',30)
    deadline=time.monotonic()+timeout
    prompt=_PROMPT.replace('{instructions}',instructions).replace('{documents}',''.join(
        f'\n===== BEGIN {Path(path).name} =====\n{text}\n===== END =====\n' for path,text in documents.items()))
    with tempfile.TemporaryDirectory(prefix='dachapply-literal-',ignore_cleanup_errors=True) as workdir:
        try:
            answer=run_structured_model(prompt,EDIT_SCHEMA,provider,model,workdir=workdir,
                                        cancelled=lambda: bool(cancelled and cancelled()) or time.monotonic() > deadline)
        except GenerationCancelled:
            if cancelled and cancelled():
                raise
            raise NotLiteral(f'the local model did not answer within {timeout:g}s') from None
        except Exception:
            raise NotLiteral('the local model failed') from None
    edits=answer.get('edits')
    if answer.get('literal') is not True:
        raise NotLiteral('the local model judged the request not literal')
    if not isinstance(edits,list) or not edits or not all(isinstance(edit,dict) and isinstance(edit.get('old'),str) and isinstance(edit.get('new'),str) for edit in edits):
        raise NotLiteral('the local model returned no usable edits')
    return [(edit['old'],edit['new']) for edit in edits]
