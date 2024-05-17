from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from session import Session

NAME = 'Right Stuf'

PATH = re.compile(r'(?P<path>/[^/]+)(?:/.*)?')


def equal(a: str, b: str) -> bool:
    match_a = PATH.fullmatch(urlparse(a).path)
    match_b = PATH.fullmatch(urlparse(b).path)
    return (match_a and match_b
            and match_a.group('path') == match_b.group('path'))


def hash_link(link: str) -> int:
    return hash(PATH.fullmatch(urlparse(link).path).group('path'))


def normalise(session: Session, link: str) -> str | None:
    u = urlparse(link)
    if not PATH.fullmatch(u.path):
        return None
    return urlunparse(('https', 'legacy.rightstufanime.com', u.path, '', '', ''))
