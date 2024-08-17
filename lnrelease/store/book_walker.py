from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from session import Session

NAME = 'BOOK☆WALKER'
SALT = hash(NAME)

PATH = re.compile(r'(?P<path>/[a-f\d]{10}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12})(?:/.*)?')


def equal(a: str, b: str) -> bool:
    match_a = PATH.fullmatch(urlparse(a).path)
    match_b = PATH.fullmatch(urlparse(b).path)
    return (match_a and match_b
            and match_a.group('path') == match_b.group('path'))


def hash_link(link: str) -> int:
    return SALT + hash(PATH.fullmatch(urlparse(link).path).group('path'))


def normalise(session: Session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = match.group('path') + '/'
    else:
        return None
    return urlunparse(('https', u.netloc, path, '', '', ''))
