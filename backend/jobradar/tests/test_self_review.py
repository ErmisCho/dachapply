from unittest import mock

from jobradar.services import self_review
from jobradar.services.self_review import apply_review_fixes, build_review_prompt, review_documents

CV='/x/Name-CV-Acme.tex'
LETTER='/x/Name-Letter-Acme.tex'
KINDS={CV:'cv',LETTER:'letter'}


def fix(old,new,file='cv'):
    return {'severity':'blocking','category':'other','file':file,'explanation':'x','old':old,'new':new}


def test_prompt_contains_everything():
    prompt=build_review_prompt({CV:'\\textbf{Python} {a}'},'POSTING-TEXT','EVIDENCE-TEXT',['CLAIM-X'],'German')
    for needle in ('POSTING-TEXT','EVIDENCE-TEXT','\\textbf{Python} {a}','CLAIM-X','German','HONESTY RULE','not in the EVIDENCE'):
        assert needle in prompt


def test_review_returns_findings():
    good=fix('a','b')
    with mock.patch.object(self_review,'run_structured_model',return_value={'findings':[good,{'junk':1}]}):
        assert review_documents({CV:'a'},'p','e','ollama','m') == [good]


def test_review_empty_on_exception_and_malformed():
    with mock.patch.object(self_review,'run_structured_model',side_effect=RuntimeError('boom')):
        assert review_documents({CV:'a'},'p','e','ollama','m') == []
    with mock.patch.object(self_review,'run_structured_model',return_value={'findings':'nope'}):
        assert review_documents({CV:'a'},'p','e','ollama','m') == []


def test_review_reraises_user_cancel_only():
    cancelled=self_review.GenerationCancelled
    with mock.patch.object(self_review,'run_structured_model',side_effect=cancelled()):
        assert review_documents({CV:'a'},'p','e','ollama','m',cancelled=lambda: False) == []
        try:
            review_documents({CV:'a'},'p','e','ollama','m',cancelled=lambda: True)
        except cancelled:
            return
    raise AssertionError('user cancel must propagate')


def test_unique_fix_changes_only_the_span():
    docs={CV:'head\nI hold a PMP certificate.\ntail\n',LETTER:'I hold a PMP certificate.'}
    updates,applied,dropped=apply_review_fixes(docs,[fix('I hold a PMP certificate.\n','')],KINDS)
    assert updates == {CV:'head\ntail\n'} and len(applied) == 1 and dropped == []


def test_repeated_old_is_replaced_everywhere():
    docs={CV:'Dev A\nmid\nDev A\n',LETTER:'Dev A stays'}
    updates,applied,dropped=apply_review_fixes(docs,[fix('Dev A','Dev B')],KINDS)
    assert updates == {CV:'Dev B\nmid\nDev B\n'} and len(applied) == 1


def test_missing_old_dropped_with_reason():
    updates,applied,dropped=apply_review_fixes({CV:'abc'},[fix('zzz','y'),fix('','y'),fix('abc','abc')],KINDS)
    assert updates == {} and applied == []
    assert [reason for _,reason in dropped] == ['OLD not found exactly','empty OLD','OLD equals NEW']


def test_overlap_dropped():
    updates,applied,dropped=apply_review_fixes({CV:'one two three'},[fix('one two','X'),fix('two three','Y')],KINDS)
    assert updates == {CV:'X three'} and dropped[0][1] == 'overlaps an earlier fix'


def test_crlf_document():
    docs={CV:'a\r\nb line\r\nc\r\n'}
    updates,applied,dropped=apply_review_fixes(docs,[fix('b line\nc','B\nC')],KINDS)
    assert updates == {CV:'a\r\nB\r\nC\r\n'}
