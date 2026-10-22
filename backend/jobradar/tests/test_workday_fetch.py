"""TASK-341: a Workday posting is read from Workday's cxs JSON endpoint, keeping its headings and
bullets on their own lines (the page itself flattens them; measured on job 1533: 5 lines)."""
import json

from jobradar.services import posting_fetch

HTML = ('<p>Founded in 1968, ACME is a global partner.</p><p></p><p><b>The role</b></p><p><span>You design data pipelines.</span></p>'
        '<p><b>How you’ll make an impact</b></p><ul><li>Advise customers</li><li>Build platforms</li></ul>'
        '<p><b>What’s important to us</b></p><ul><li>Strong Python and SQL skills</li></ul>'
        '<p><b>What we offer</b></p><p>An annual salary of EUR 60,000 gross.</p>')
ANSWER = {'jobPostingInfo': {'title': 'Data Engineer', 'jobDescription': HTML, 'location': 'Vienna'},
          'hiringOrganization': {'name': '1006 ACME Engineering (Austria) GmbH'}}


def test_a_workday_link_is_read_from_the_cxs_endpoint_with_its_structure(monkeypatch):
    calls = []
    monkeypatch.setattr(posting_fetch, '_download', lambda url, *a, **k: calls.append(url) or (json.dumps(ANSWER), url))
    text, company = posting_fetch._workday_text('https://acme.wd3.myworkdayjobs.com/en-US/ACME-Careers/job/Vienna/Data-Engineer_JR1')
    assert calls == ['https://acme.wd3.myworkdayjobs.com/wday/cxs/acme/ACME-Careers/job/Vienna/Data-Engineer_JR1']
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert lines[0] == 'Data Engineer' and 'The role' in lines and 'How you’ll make an impact' in lines
    assert 'Advise customers' in lines and lines[-1] == 'Location: Vienna'
    assert company == 'ACME Engineering (Austria) GmbH'
    assert posting_fetch.missing_parts(text) == []  # 'make an impact' / 'the role' count as tasks


def test_other_links_and_failures_fall_back(monkeypatch):
    def boom(*a, **k):
        raise OSError('down')
    monkeypatch.setattr(posting_fetch, '_download', boom)
    assert posting_fetch._workday_text('https://acme.wd3.myworkdayjobs.com/ACME-Careers/job/Vienna/X_JR1') == ('', '')
    assert posting_fetch._workday_text('https://example.org/jobs/1') == ('', '')
    assert posting_fetch._workday_text('https://acme.wd3.myworkdayjobs.com/ACME-Careers') == ('', '')
