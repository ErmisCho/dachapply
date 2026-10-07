from types import SimpleNamespace

import pytest

from jobradar.services.cv_generator import _package_filename, _target_names, _target_slug


def _job(company, title):
    return SimpleNamespace(company=company, title=title)


def test_owner_example_names_cv_letter_and_package_alike():
    # TASK-270 AC1: the owner's file, and the same target part on all three artifacts.
    job=_job('Accenture','AI Engineer for Generative AI (All Genders)')
    target='Accenture-AI-Engineer-For-Generative-AI'
    assert _target_names(job,'Chorinopoulos-Ermis','Anschreiben')==(
        f'Chorinopoulos-Ermis-CV-{target}.tex',f'Chorinopoulos-Ermis-Anschreiben-{target}.tex')
    assert _package_filename(job,'Chorinopoulos-Ermis')==f'Chorinopoulos-Ermis-Application-{target}.zip'


@pytest.mark.parametrize('company,title,expected',[
    # AC2: AI is AI whatever its case; compounds written with AI keep it; plain "ai" letters do not.
    ('Acme','ai engineer','Acme-AI-Engineer'),
    ('Acme','Ai Engineer','Acme-AI-Engineer'),
    ('Acme','Applied AI-Engineer','Acme-Applied-AI-Engineer'),
    ('Acme','GenAI Developer','Acme-GenAI-Developer'),
    ('OpenAI','Research Engineer','OpenAI-Research-Engineer'),
    ('Mainz AG','Training Lead','Mainz-Ag-Training-Lead'),
    ('Acme','Maintenance Engineer, Mainz','Acme-Maintenance-Engineer-Mainz'),
    ('Acme','MAINTENANCE ENGINEER','Acme-Maintenance-Engineer'),
    # AC3: gender markers anywhere, EN and DE, and the separator they leave behind.
    ('Acme','Data Engineer (all genders)','Acme-Data-Engineer'),
    ('Acme','Data Engineer all genders','Acme-Data-Engineer'),
    ('Acme','Data Engineer (m/w/d)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (w/m/d)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (m/f/d)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (f/m/x)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (d/f/m)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (m/w/x)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (gn)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (gn*)','Acme-Data-Engineer'),
    ('Acme','Data Engineer (alle Geschlechter)','Acme-Data-Engineer'),
    ('Acme','Data Engineer m/w/d','Acme-Data-Engineer'),
    ('Acme','Data Engineer (m/w/d) - Vienna','Acme-Data-Engineer-Vienna'),
    ('Acme','(m/w/d) Data Engineer','Acme-Data-Engineer'),
    ('Acme','Data Engineer - (m/w/d)','Acme-Data-Engineer'),
    ('Acme','Data Engineer | all genders','Acme-Data-Engineer'),
    ('Acme','Data Engineer, (gn*)','Acme-Data-Engineer'),
    ('Acme','Softwareentwickler*in Backend','Acme-Softwareentwickler-Backend'),
    ('Acme','Softwareentwickler:in','Acme-Softwareentwickler'),
    ('Acme','Softwareentwickler_in','Acme-Softwareentwickler'),
    ('Acme','Softwareentwickler/-in','Acme-Softwareentwickler'),
    ('Acme','Berater*innen im Vertrieb','Acme-Berater-Im-Vertrieb'),
    # AC4: TÜV stays TUV; words with "in" are not gender markers.
    ('TÜV AUSTRIA','Machine Learning Engineer (gn*)','TUV-Austria-Machine-Learning-Engineer'),
    ('Acme','Engineer in Vienna','Acme-Engineer-In-Vienna'),
])
def test_target_slug(company, title, expected):
    assert _target_slug(_job(company,title))==expected


def test_target_slug_keeps_the_90_character_cap():
    assert len(_target_slug(_job('Acme','AI '*60)))==90
