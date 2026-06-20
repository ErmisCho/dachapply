from config.settings import normalize_smtp_password


def test_normalize_smtp_password_removes_gmail_app_password_group_spaces():
    assert normalize_smtp_password('smtp.gmail.com', 'abcd efgh ijkl mnop') == 'abcdefghijklmnop'


def test_normalize_smtp_password_preserves_non_gmail_password_spaces():
    password = 'keep spaces for another provider'
    assert normalize_smtp_password('smtp.example.com', password) == password


def test_normalize_smtp_password_preserves_non_app_password_shape():
    password = 'not a 16 char app password'
    assert normalize_smtp_password('smtp.gmail.com', password) == password
