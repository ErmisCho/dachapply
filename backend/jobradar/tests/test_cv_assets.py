"""TASK-99a: templates and the photograph belong to one account and reach no other.

The photograph in every test here is a three-byte fixture. The owner's real photo, like
Ermis-Chorinopoulos-Candidate-Evidence.md, is personal data that is deliberately untracked
(CLAUDE.md) and no test may depend on it.
"""
import json
from io import StringIO
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from jobradar.models import CvAsset, JobLead
from jobradar.services import cv_generator
from jobradar.services.cv_generator import generate_cv_package, generation_preview, user_photo, user_templates

GERMAN_SOURCE = 'Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben.'


@pytest.fixture
def german_job(db):
    user = User.objects.create_user('job-owner')
    return JobLead.objects.create(company='Firma', title='Entwickler', raw_description=GERMAN_SOURCE, created_by=user)


def test_one_accounts_templates_and_photo_are_unreachable_by_another(db, cv_assets, german_job):
    """AC4. This fails the moment the lookup is widened past `filter(user=...)`.

    Three separate widenings are covered, because each is a plausible thing to add later:

    1. Falling back to another account's row when this one has none -- 'the only template in the
       database', or the CODEX_CV_OWNER_EMAIL account's, or a bundled default.
    2. Returning every row rather than this account's, which would make A's option list contain B's
       templates even when A has its own.
    3. Falling back for the photograph specifically, which is the one that would put the owner's
       face on a stranger's CV.
    """
    alice = User.objects.create_user('alice@example.test', email='alice@example.test')
    bob = User.objects.create_user('bob@example.test', email='bob@example.test')
    cv_assets(alice, cv_source='ALICE CV', letter_source='ALICE LETTER', photo=b'alice-photo')
    cv_assets(bob, cv_source='BOB CV', letter_source='BOB LETTER', photo=b'bob-photo')

    alice_templates = user_templates(alice)
    assert {language: entry['cv'].source for language, entry in alice_templates.items()} == {'en': 'ALICE CV', 'de': 'ALICE CV'}
    assert all(asset.source == 'ALICE LETTER' for entry in alice_templates.values() for asset in entry['letters'].values())
    assert bytes(user_photo(alice).image) == b'alice-photo'
    assert not any('BOB' in asset.source for asset in cv_generator.user_cv_assets(alice))

    # An account with nothing stored gets nothing. No inheritance, no default, no owner fallback.
    carol = User.objects.create_user('carol@example.test', email='carol@example.test')
    assert user_templates(carol) == {} and user_photo(carol) is None
    assert cv_generator.user_cv_assets(carol) == []
    assert generation_preview(german_job, carol)['cvs'] == []
    assert generation_preview(german_job, carol)['configured'] is False
    assert 'No CV template is stored on this account' in generation_preview(german_job, carol)['unavailable_reason']

    # Anonymous and None resolve to nothing rather than to whoever happens to be first in the table.
    assert cv_generator.user_cv_assets(None) == [] and user_templates(None) == {} and user_photo(None) is None

    # And the option list a user is offered contains only their own labels.
    bob_only = CvAsset.objects.filter(user=bob).update(label='BOB LABEL')
    assert bob_only and all(cv['label'] != 'BOB LABEL' for cv in generation_preview(german_job, alice)['cvs'])

    # Deleting the account takes its templates and photograph with it rather than orphaning a
    # megabyte of somebody's face in a table nobody looks at.
    bob.delete()
    assert not CvAsset.objects.filter(user_id=bob.pk).exists() and CvAsset.objects.filter(user=alice).count() == 7


def _fake_pdflatex(monkeypatch, generated):
    """A model CLI and a pdflatex that succeed, so the test asserts about inputs, not compilation."""
    from pathlib import Path

    seen = {'commands': [], 'dirs': [], 'tex': [], 'photo': [], 'written_bytes': []}

    def fake_run(command, **kwargs):
        seen['commands'].append(command)
        if command[0] == 'pdfinfo':
            return SimpleNamespace(returncode=0, stdout='Pages: 1\nPage size: 612 x 792 pts', stderr='')
        if command[0] == 'codex':
            # What the model was actually handed: the exact bytes in the compile directory.
            output = Path(command[command.index('--cd') + 1])
            seen['dirs'].append(sorted(path.name for path in output.iterdir()))
            seen['tex'].append('\n'.join(path.read_text(encoding='utf-8') for path in sorted(output.glob('*.tex'))))
            photo = output / 'Picture.jpg'
            seen['photo'].append(photo.read_bytes() if photo.is_file() else None)
            seen['written_bytes'].append(b''.join(path.read_bytes() for path in sorted(output.glob('*.tex'))))
            Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(generated))
            return SimpleNamespace(returncode=0, stdout='ok', stderr='')
        (Path(kwargs['cwd']) / Path(command[-1]).with_suffix('.pdf')).write_bytes(b'pdf')
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')

    monkeypatch.setattr('jobradar.services.cv_generator.shutil.which', lambda command: command)
    monkeypatch.setattr('jobradar.services.cv_generator.available_model_options', lambda: [
        {'provider': 'openai', 'key': 'gpt-5.5', 'label': 'GPT-5.5', 'efforts': ['medium'], 'default_effort': 'medium', 'fast_tier': ''},
    ])
    monkeypatch.setattr('jobradar.services.cv_generator.subprocess.run', fake_run)
    return seen


VALID_TEX = '\\documentclass{article}\\begin{document}tailored\\end{document}'
GENERATED = {'cv_tex': VALID_TEX, 'changed_files': ['cv.tex'], 'main_changes': ['Tailored'],
             'unsupported_requirements_not_claimed': [], 'confirmations': {
                 'cv_max_2_pages': True, 'letter_max_1_page': True, 'no_orphaned_employer_headings': True,
                 'no_text_overlap': True, 'nothing_after_end_document': True, 'links_work': True,
                 'photo_loads_if_used': True, 'no_invented_tools_or_overclaims': True}}


def test_generation_uses_the_requesting_accounts_own_template_and_photo(db, tmp_path, monkeypatch, settings, cv_assets, german_job):
    """AC1/AC2 through the real entry point, not just the lookup helper."""
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_CACHE = False; settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir()
    alice = User.objects.create_user('alice-gen@example.test', email='alice-gen@example.test')
    bob = User.objects.create_user('bob-gen@example.test', email='bob-gen@example.test')
    cv_assets(alice, cv_source='ALICE TEMPLATE', photo=b'alice-photo')
    cv_assets(bob, cv_source='BOB TEMPLATE', photo=b'bob-photo')
    seen = _fake_pdflatex(monkeypatch, GENERATED)

    generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=alice.id)
    # The model was handed Alice's template and Alice's photograph, and nothing of Bob's.
    assert seen['tex'][-1] == 'ALICE TEMPLATE' and seen['photo'][-1] == b'alice-photo'
    assert 'Picture.jpg' in seen['dirs'][-1]

    # Bob generating the same job gets his own bytes; the two never meet even though the workspace
    # they write into is shared.
    generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=bob.id)
    assert seen['tex'][-1] == 'BOB TEMPLATE' and seen['photo'][-1] == b'bob-photo'

    # A user with no templates cannot borrow one by asking for a language somebody else has.
    carol = User.objects.create_user('carol-gen@example.test', email='carol-gen@example.test')
    with pytest.raises(ValueError, match='Select a CV template'):
        generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=carol.id)
    # ...and neither can an unauthenticated/absent user id, which used to reach the workspace files.
    with pytest.raises(ValueError, match='Select a CV template'):
        generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium')


def test_an_account_with_no_photo_is_told_so_instead_of_failing_in_latex(db, tmp_path, monkeypatch, settings, cv_assets, german_job):
    """AC2: the documented outcome for a user who has no photograph.

    Refused up front with the reason when their own template asks for one; generated normally when
    it does not. Never another account's photo, and never two automatic model repair attempts spent
    on a missing file no LaTeX rewrite can produce.
    """
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_CACHE = False; settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir()
    seen = _fake_pdflatex(monkeypatch, GENERATED)

    with_photo = User.objects.create_user('has-photo@example.test', email='has-photo@example.test')
    cv_assets(with_photo, photo=b'jpg')
    without = User.objects.create_user('no-photo@example.test', email='no-photo@example.test')
    cv_assets(without, cv_source='\\documentclass{article}\\includegraphics{./Picture.jpg}', photo=None)

    with pytest.raises(RuntimeError, match='no photo is stored on this account'):
        generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=without.id)
    assert not any(command[0] == 'codex' for command in seen['commands']), 'refused before spending a model call'

    # A template that does not ask for a photograph generates without one, and no file is invented.
    CvAsset.objects.filter(user=without, kind=CvAsset.KIND_CV).update(source='\\documentclass{article} no photo here')
    generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=without.id)
    assert seen['dirs'] and 'Picture.jpg' not in seen['dirs'][-1]


def test_two_accounts_with_identical_templates_do_not_share_a_cached_package(db, tmp_path, monkeypatch, settings, cv_assets, german_job):
    """The package cache directory is shared by the whole machine, so the account is in its key.

    Before TASK-99a the key was job + profile + options + template bytes. Two accounts with the
    same template hashed to the same entry, and the cached zip carries the FIRST account's surname
    in its filenames -- so the second downloaded an application titled with a stranger's name.
    """
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_CACHE = True; settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir()
    seen = _fake_pdflatex(monkeypatch, GENERATED)
    alice = User.objects.create_user('alice-cache@example.test', email='alice-cache@example.test', first_name='Alice', last_name='Ant')
    bob = User.objects.create_user('bob-cache@example.test', email='bob-cache@example.test', first_name='Bob', last_name='Bee')
    for user in (alice, bob):
        cv_assets(user, cv_source='IDENTICAL TEMPLATE', photo=b'jpg')

    _, _, alice_saved = generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=alice.id)
    model_calls = sum(command[0] == 'codex' for command in seen['commands'])
    _, _, bob_saved = generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=bob.id)
    assert sum(command[0] == 'codex' for command in seen['commands']) == model_calls + 1, "Bob must not be served Alice's cached package"
    assert 'Ant-Alice' in alice_saved['cv_tex'] and 'Bee-Bob' in bob_saved['cv_tex']

    # Alice asking again IS served from the cache -- the key is narrowed by account, not broken.
    _, _, again = generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=alice.id)
    assert sum(command[0] == 'codex' for command in seen['commands']) == model_calls + 1 and again == alice_saved


def test_import_command_is_dry_run_by_default_and_prints_a_before_after_census(db, tmp_path):
    """AC3: the owner's files move with a command they can inspect first, never a migration."""
    owner = User.objects.create_user('import-owner@example.test', email='import-owner@example.test')
    workspace = tmp_path / 'latex'
    (workspace / 'CVs').mkdir(parents=True)
    (workspace / 'CVs' / 'English - AI Engineer (base)_v_1.3.tex').write_text('old english', encoding='utf-8')
    (workspace / 'CVs' / 'English - AI Engineer (base)_v_1.5.tex').write_text('newest english', encoding='utf-8')
    (workspace / 'CVs' / 'German - AI Engineer (base)_v_1.3.tex').write_text('german cv', encoding='utf-8')
    (workspace / 'CVs' / 'Picture.jpg').write_bytes(b'photo-bytes')
    (workspace / 'Motivation_letter.tex').write_text('english letter', encoding='utf-8')
    (workspace / 'Motivationsschreiben.tex').write_text('deutscher brief', encoding='utf-8')

    out = StringIO()
    call_command('import_cv_assets', '--user', 'import-owner@example.test', '--workspace', str(workspace), stdout=out)
    census = out.getvalue()
    assert 'Dry run' in census and 'Nothing changed' in census
    assert CvAsset.objects.count() == 0, 'a dry run writes nothing'
    # The census names every asset with its size, so the owner can compare before and after.
    assert '(none)' in census and f'{len(b"photo-bytes")} B' in census
    assert 'English - AI Engineer (base)_v_1.5.tex' in census and 'Bewerbungsschreiben' in census  # newest version, and what is missing

    out = StringIO()
    call_command('import_cv_assets', '--user', 'import-owner@example.test', '--workspace', str(workspace), '--apply', stdout=out)
    assert 'now has 5' in out.getvalue()
    templates = user_templates(owner)
    assert templates['en']['cv'].source == 'newest english' and templates['en']['cv'].filename.endswith('_v_1.5.tex')
    assert templates['de']['letters']['motivationsschreiben'].source == 'deutscher brief'
    assert bytes(user_photo(owner).image) == b'photo-bytes' and user_photo(owner).filename == 'Picture.jpg'
    assert templates['en']['cv'].source_path == str(workspace / 'CVs' / 'English - AI Engineer (base)_v_1.5.tex')

    # Re-running refreshes in place rather than duplicating: this is how a template edited in the
    # workspace gets back into the account.
    (workspace / 'CVs' / 'German - AI Engineer (base)_v_1.3.tex').write_text('edited german cv', encoding='utf-8')
    out = StringIO()
    call_command('import_cv_assets', '--user', 'import-owner@example.test', '--workspace', str(workspace), '--apply', stdout=out)
    assert CvAsset.objects.filter(user=owner).count() == 5 and 'updated cv/de' in out.getvalue()
    assert user_templates(owner)['de']['cv'].source == 'edited german cv'

    # The import is per account and names it explicitly; it never guesses.
    with pytest.raises(CommandError, match='matched 0 accounts'):
        call_command('import_cv_assets', '--user', 'nobody@example.test', '--workspace', str(workspace))
    with pytest.raises(CommandError, match='not a directory'):
        call_command('import_cv_assets', '--user', 'import-owner@example.test', '--workspace', str(tmp_path / 'gone'))
    assert not CvAsset.objects.exclude(user=owner).exists()


def test_the_template_handed_to_the_model_is_byte_identical_to_the_stored_source(db, tmp_path, monkeypatch, settings, cv_assets, german_job):
    """AC5's mechanism: storing a template must not change one byte of what gets generated from.

    These files were shutil.copy2'd before TASK-99a. Writing them out of the database instead puts
    Python's newline translation in the path, and on Windows that turns every LF into CRLF -- the
    owner's templates are LF-only, so without an explicit newline the model would be handed a file
    that differs from the one it was handed before, on every single line.
    """
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_CACHE = False; settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir()
    source = '\\documentclass{article}\n\\begin{document}\nline one\nline two\n\\end{document}\n'
    user = User.objects.create_user('bytes@example.test', email='bytes@example.test')
    cv_assets(user, cv_source=source, photo=b'jpg')
    seen = _fake_pdflatex(monkeypatch, GENERATED)

    generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=user.id)
    assert seen['written_bytes'][-1] == source.encode('utf-8'), 'newline translation changed the template'


def test_readjusting_a_document_that_is_gone_from_the_workspace_says_so(db, tmp_path, monkeypatch, settings, cv_assets, german_job):
    """The workspace is an ordinary directory the owner also files things in by hand.

    Before TASK-99a a missing previous document was caught by the same existence check that covered
    the template files. The template is a row now, so this path needed its own message rather than a
    raw FileNotFoundError with an absolute path in it.
    """
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_CACHE = False; settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir()
    user = User.objects.create_user('gone@example.test', email='gone@example.test')
    cv_assets(user)
    _fake_pdflatex(monkeypatch, GENERATED)

    with pytest.raises(RuntimeError, match='no longer on disk'):
        generate_cv_package(german_job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium',
                            source_cv=str(tmp_path / 'CVs' / 'deleted.tex'), revision_instructions='shorten',
                            user_id=user.id)
