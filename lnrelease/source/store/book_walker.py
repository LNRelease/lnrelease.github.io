import re
from urllib.parse import urlparse, urlunparse

NAME = 'BOOK☆WALKER'

PATH = re.compile(r'(?P<path>/[a-f\d]{10}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12})(?:/.*)?')


def normalise(session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = match.group('path') + '/'
    else:
        return None
    return urlunparse(('https', u.netloc, path, '', '', ''))
