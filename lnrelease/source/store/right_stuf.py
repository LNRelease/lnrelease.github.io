import re
from urllib.parse import urlparse, urlunparse

NAME = 'Right Stuf'

PATH = re.compile(r'(?P<path>/[^/]+)(?:/.*)?')


def normalise(session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = match.group('path')
    else:
        return None
    return urlunparse(('https', 'www.rightstufanime.com', path, '', '', ''))
