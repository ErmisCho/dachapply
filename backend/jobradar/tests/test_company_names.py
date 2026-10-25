"""TASK-346: junk company names never replace the placeholder, and a job board's JSON-LD employer names a
link-only job at fetch time (2026-10-25: job 1937 was named 'Unknown company; posting refers to MP')."""
import json

from jobradar.services import posting_fetch
from jobradar.services.json_importer import is_placeholder_label


def test_junk_company_names_count_as_placeholders():
    assert is_placeholder_label('company', 'Unknown company; posting refers to MP')
    assert is_placeholder_label('company', 'Unknown company') and is_placeholder_label('company', '')
    assert not is_placeholder_label('company', 'MP Corporate Finance GmbH')
    assert not is_placeholder_label('company', 'FERCHAU GmbH client not disclosed')  # an accepted real-world label


def test_the_json_ld_employer_is_read():
    posting = {'@context': 'https://schema.org', '@type': 'JobPosting', 'title': 'Engineer', 'description': '<p>Build</p>',
               'hiringOrganization': {'@type': 'Organization', 'name': ' MP Corporate Finance GmbH '}}
    page = f'<html><head><script type="application/ld+json">{json.dumps(posting)}</script></head><body>x</body></html>'
    assert posting_fetch._json_ld_company(page) == 'MP Corporate Finance GmbH'
    assert posting_fetch._json_ld_company('<html><body>no structured data</body></html>') == ''
