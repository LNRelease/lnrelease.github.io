from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from session import Session

NAME = 'VIZ Media'
SALT = hash(NAME)

PATH = re.compile(r'/read/novel/(?P<name>[\w-]+)/product/(?P<id>\d+)/(?P<format>\w+)')


def equal(a: str, b: str) -> bool:
    match_a = PATH.fullmatch(urlparse(a).path)
    match_b = PATH.fullmatch(urlparse(b).path)
    return (match_a and match_b
            and match_a.group('id') == match_b.group('id')
            and match_a.group('format') == match_b.group('format'))


def hash_link(link: str) -> int:
    match = PATH.fullmatch(urlparse(link).path)
    return SALT + hash(match.group('id') + match.group('format'))


def normalise(session: Session, link: str) -> str | None:
    u = urlparse(link)
    if not PATH.fullmatch(u.path):
        return None
    return urlunparse(('https', 'www.viz.com', u.path, '', '', ''))
