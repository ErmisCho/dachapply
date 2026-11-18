"""TASK-385: one automatic review round over a generated CV + cover letter.

The model proposes exact OLD/NEW fixes; nothing is applied unless OLD is found in the documents,
and only the matched spans change. The honesty rule lives in the prompt (the model never sees a
reason to add unsupported content) -- wiring and any word-level gate are a later task.
"""
import logging
import tempfile
import time
from pathlib import Path

from django.conf import settings

from jobradar.services.cv_generator import GenerationCancelled, match_exact_pair, replace_every_copy, run_structured_model
from jobradar.services.literal_edits import words

logger=logging.getLogger(__name__)

CATEGORIES=['unsupported_claim','posting_fit','letter_quality','stray_text','language','layout','other']
REVIEW_SCHEMA={
    'type':'object',
    'properties':{'findings':{'type':'array','items':{'type':'object','properties':{
        'severity':{'type':'string','enum':['blocking','improve']},
        'category':{'type':'string','enum':CATEGORIES},
        'file':{'type':'string','enum':['cv','letter']},
        'explanation':{'type':'string'},
        'old':{'type':'string'},
        'new':{'type':'string'},
    },'required':['severity','category','file','explanation','old','new'],'additionalProperties':False}}},
    'required':['findings'],
    'additionalProperties':False,
}

_PROMPT='''Act as a strict senior recruiter and hiring manager reviewing a tailored CV and cover letter for THIS posting only.

Look for, in this order:
- unsupported_claim: any certificate, language level, tool, skill, employer, metric or claim that the EVIDENCE does not support.
- stray_text: instruction or meta text left inside a document (e.g. notes to the writer, placeholders, text that does not belong in its section).
- language: text in a different language than the posting/letter language{language}.
- posting_fit: headline, profile or skills that do not mirror the posting's top requirements.
- letter_quality: letter paragraphs that repeat CV bullets, or are generic and could be sent to any employer.
- layout: lines or entries that will clearly break the page fit or the formatting.

HONESTY RULE: never introduce any skill, tool, certificate, language level, employer, metric or claim that is not in the EVIDENCE. A fix may only remove, reorder or rephrase supported content, or mirror the posting's wording for skills the EVIDENCE supports.

Each finding is an exact replacement: "old" is copied character for character from the documents (LaTeX included) and is unique, or intentionally repeated if every copy must change; "new" is the replacement. To delete text, make "new" the empty remainder of the line. Report at most 12 findings, prefer few high-value fixes, and return {{"findings": []}} if the documents are already strong. Answer JSON only.
{flagged}
POSTING:
<<<
{posting}
>>>

EVIDENCE (the only source of truth about the candidate):
<<<
{evidence}
>>>

DOCUMENTS:
{documents}'''


def build_review_prompt(documents, posting_text, evidence_text, flagged_claims=(), language_hint=''):
    flagged=''
    if flagged_claims:
        flagged='\nMUST CHECK (an automatic claim guard flagged these as possibly unsupported):\n'+''.join(f'- {claim}\n' for claim in flagged_claims)
    # Not str.format: the documents are full of LaTeX braces.
    return (_PROMPT.replace('{{','{').replace('}}','}')
            .replace('{language}',f' ({language_hint})' if language_hint else '')
            .replace('{flagged}',flagged).replace('{posting}',posting_text).replace('{evidence}',evidence_text)
            .replace('{documents}',''.join(f'\n===== BEGIN {Path(path).name} =====\n{text}\n===== END =====\n' for path,text in documents.items())))


def review_documents(documents, posting_text, evidence_text, provider, model, effort='default', speed='normal',
                     flagged_claims=(), cancelled=None, timeout=None):
    """Findings from one model review round. Never raises except GenerationCancelled when the user
    cancelled; a failure, timeout or malformed answer yields [] (the documents just ship unreviewed)."""
    timeout=timeout if timeout is not None else getattr(settings,'CODEX_CV_SELF_REVIEW_TIMEOUT',300)
    deadline=time.monotonic()+timeout
    prompt=build_review_prompt(documents,posting_text,evidence_text,flagged_claims)
    with tempfile.TemporaryDirectory(prefix='dachapply-review-',ignore_cleanup_errors=True) as workdir:
        try:
            answer=run_structured_model(prompt,REVIEW_SCHEMA,provider,model,effort,speed,workdir=workdir,
                                        cancelled=lambda: bool(cancelled and cancelled()) or time.monotonic() > deadline)
        except GenerationCancelled:
            if cancelled and cancelled():
                raise
            logger.warning('self-review timed out after %ss',timeout)
            return []
        except Exception:
            logger.warning('self-review failed',exc_info=True)
            return []
    findings=answer.get('findings') if isinstance(answer,dict) else None
    if not isinstance(findings,list):
        logger.warning('self-review returned malformed findings')
        return []
    return [item for item in findings if isinstance(item,dict) and item.get('file') in ('cv','letter')
            and isinstance(item.get('old'),str) and isinstance(item.get('new'),str)]


def _spans(documents, old, new):
    """[(path, start, end, replacement)] for one fix, or a reason string when it cannot be applied."""
    if not old.strip():
        return 'empty OLD'
    if old == new:
        return 'OLD equals NEW'
    match=match_exact_pair(documents,old,new)
    if match and match[0]:
        return [match]
    if match:
        return 'already applied'
    copies=replace_every_copy(documents,old,new)
    if not copies:
        return 'OLD not found exactly' if copies is None else 'already applied'
    spans=[]
    for path in copies:
        for candidate,replacement in ((old,new),(old.replace('\n','\r\n'),new.replace('\n','\r\n'))):
            if candidate in documents[path]:
                start=documents[path].find(candidate)
                while start != -1:
                    spans.append((path,start,start+len(candidate),replacement))
                    start=documents[path].find(candidate,start+len(candidate))
                break
    return spans


def apply_review_fixes(documents, findings, kinds):
    """(updates {path: text}, applied findings, dropped [(finding, reason)]). `kinds` maps each
    document path to 'cv' or 'letter'. Only matched spans change; a fix that overlaps an earlier one is dropped."""
    taken={}
    applied=[]
    dropped=[]
    for finding in findings:
        scope={path:text for path,text in documents.items() if kinds.get(path) == finding.get('file')}
        spans=_spans(scope,finding.get('old') or '',finding.get('new') or '') if scope else 'no such document'
        if isinstance(spans,str):
            dropped.append((finding,spans))
        elif any(start < end2 and start2 < end for path,start,end,_ in spans for start2,end2,_ in taken.get(path,())):
            dropped.append((finding,'overlaps an earlier fix'))
        else:
            for path,start,end,replacement in spans:
                taken.setdefault(path,[]).append((start,end,replacement))
            applied.append(finding)
    updates={}
    for path,items in taken.items():
        text=documents[path]
        for start,end,replacement in sorted(items,reverse=True):
            text=text[:start]+replacement+text[end:]
        updates[path]=text
    return updates,applied,dropped


def harden_findings(findings, evidence_text, posting_text):
    """(kept, dropped [(finding, reason)]): the word-level no-invented-content gate. A wildcard OLD
    ('...' alone on a line) or a NEW with a word found in neither its OLD, the evidence nor the posting is dropped."""
    known=words(evidence_text)|words(posting_text)
    kept=[]
    dropped=[]
    for finding in findings:
        old,new=finding.get('old') or '',finding.get('new') or ''
        if any(line.strip() == '...' for line in old.splitlines()):
            dropped.append((finding,'wildcard OLD'))
            continue
        invented=sorted(words(new)-words(old)-known)
        if invented:
            dropped.append((finding,'NEW adds unsupported words: '+', '.join(invented[:8])))
        else:
            kept.append(finding)
    return kept,dropped
