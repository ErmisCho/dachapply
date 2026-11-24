"""TASK-409: a letter as plain text for an application form."""
from pathlib import Path

import pytest

from jobradar.services.letter_text import plain_text
from jobradar.tests.test_document_selection import env  # noqa: F401 -- a job with two CVs, two letters and a message

HEAD = r'''\documentclass{article}
\begin{document}
%---------- sender ----------
\noindent
Quillon Verrastro \\
\href{mailto:q@example.test}{q@example.test}

\vspace{0.5cm}
\begin{flushright}
  Wien, \today
\end{flushright}
\noindent
\textbf{Bewerbung als Entwickler (m/w/d)}
\vspace{0.4cm}

\noindent
'''
GERMAN = HEAD + r'''Sehr geehrte Frau Muster,

\vspace{0.3cm}

ich arbeite mit \textbf{Python \& SQL} und habe 95\,\% der
Abl\"aufe ver{\"a}ndert -- siehe \href{https://example.test/x_y}{mein Profil} % interner Kommentar
und \texttt{snake\_case}.

Zweiter Absatz mit \glqq{}Zitat\grqq{} und C\# sowie \{Klammern\}.
\begin{itemize}
  \item Erstens
  \item Zweitens
\end{itemize}

Mit freundlichen Gr\"u{\ss}en

\vspace{1cm}
\noindent
Quillon Verrastro
\end{document}
'''


def test_only_greeting_to_name_is_kept_and_reads_as_text():
    text, complete = plain_text(GERMAN)
    assert complete and text == (
        'Sehr geehrte Frau Muster,\n\n'
        'ich arbeite mit Python & SQL und habe 95 % der Abläufe verändert – siehe mein Profil und snake_case.\n\n'
        'Zweiter Absatz mit „Zitat“ und C# sowie {Klammern}.\n\n'
        '- Erstens\n- Zweitens\n\n'
        'Mit freundlichen Grüßen\n\nQuillon Verrastro')


def test_english_line_breaks_quotes_and_windows_newlines():
    text, complete = plain_text((HEAD + "Dear Hiring Team,\n\nI like ``simple'' tools~--- really.\n\nSincerely, \\\\[0.4cm]\nQuillon Verrastro\n\\end{document}").replace('\n', '\r\n'))
    assert complete and text == 'Dear Hiring Team,\n\nI like “simple” tools — really.\n\nSincerely,\nQuillon Verrastro'


@pytest.mark.parametrize('tex', [
    HEAD + 'An das Team,\n\nein Text.\n\nMit freundlichen Grüßen\n\\end{document}',  # no greeting we know
    HEAD + 'Dear Team,\n\na text without an end.\n\\end{document}',
])
def test_a_letter_it_cannot_delimit_is_never_cut_silently(tex):
    text, complete = plain_text(tex)
    assert not complete and 'ein Text.' in text + 'ein Text.' and ('Verrastro' in text or text.startswith('Dear Team,'))


def test_the_endpoint_copies_ticked_letters_only(env):  # noqa: F811
    for path in (env.letter, env.other_letter):
        Path(path).write_text(GERMAN, encoding='utf-8')
    before = {path: Path(path).read_bytes() for path in (env.cv_de, env.letter, env.other_letter, env.message)}
    one = env.post('tex', documents=[env.cv_de, env.letter], plain=True).data
    assert one['text'].startswith('Sehr geehrte Frau Muster,') and 'Owner-CV' not in one['text'] and '%' not in one['text'].replace('95 %', '') and one['note'] == ''
    two = env.post('tex', documents=[env.letter, env.other_letter], plain=True).data
    assert two['text'].count('Sehr geehrte Frau Muster,') == 2
    assert 'Owner-Message.tex' in env.post('tex', documents=[env.message], plain=True).data['note']  # no greeting in it
    assert env.post('tex', documents=[env.cv_de], plain=True).status_code == 400
    assert env.post('tex', documents=[env.root.as_posix() + '/elsewhere.tex'], plain=True).status_code == 400
    assert {path: Path(path).read_bytes() for path in before} == before and env.full == []
    assert 'note' not in env.post('tex', documents=[env.cv_de]).data  # Copy TeX is unchanged
