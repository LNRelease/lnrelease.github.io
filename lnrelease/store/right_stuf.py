from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import session

NAME = 'Right Stuf'

PATH = re.compile(r'(?P<path>/[^/]+)(?:/.*)?')


def equal(a: str, b: str) -> bool:
    return a == b


def hash_link(link: str) -> int:
    return hash(PATH.fullmatch(urlparse(link).path).group('path'))


def normalise(session: session.Session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = match.group('path')
    else:
        return None
    return urlunparse(('https', 'legacy.rightstufanime.com', path, '', '', ''))
