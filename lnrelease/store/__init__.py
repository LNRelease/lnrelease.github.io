from __future__ import annotations

import warnings
from urllib.parse import urlparse

import session
import utils

from . import (_default, amazon, apple, audible, barnes_noble, book_walker,
               google, kobo, prh, right_stuf, viz, yen_press)

STORES = {
    'www.amazon.ca': amazon,
    'www.amazon.co.uk': amazon,
    'www.amazon.com': amazon,
    'www.amazon.com.au': amazon,
    'www.audible.ca': audible,
    'www.audible.co.jp': audible,
    'www.audible.co.uk': audible,
    'www.audible.com': audible,
    'www.audible.com.au': audible,
    'www.audible.de': audible,
    'books.apple.com': apple,
    'itunes.apple.com': apple,
    'geo.itunes.apple.com': apple,
    'www.barnesandnoble.com': barnes_noble,
    'play.google.com': google,
    'www.kobo.com': kobo,
    'kobo.com': kobo,
    'store.kobobooks.com': kobo,
}

PROCESSED = {
    'global.bookwalker.jp': book_walker,
    'crossinfworld.com': _default,
    'hanashi.media': _default,
    'kodansha.us': _default,
    'www.penguinrandomhouse.com': prh,
    'j-novel.club': _default,
    'legacy.rightstufanime.com': right_stuf,
    'www.rightstufanime.com': right_stuf,
    'sevenseasentertainment.com': _default,
    'www.viz.com': viz,
    'yenpress.com': yen_press,
}

IGNORE = {
    'www.amazon.de',
    'www.amazon.fr',
    'www.amazon.co.jp',
    'www.bookdepository.com',
    'www.booksamillion.com',
    'bookshop.org',
    'store.crunchyroll.com',
    'books.google.com',
    'gum.co',
    'gumroad.com',
    'store.hanashi.media',
    'www.indiebound.org',
    'www.powells.com',
    'www.walmart.com',
}

RESOLVE = {
    'www.amazon.ca',
    'www.amazon.co.uk',
    'www.amazon.com',
    'www.amazon.com.au',
    'www.audible.ca',
    'www.audible.co.jp',
    'www.audible.co.uk',
    'www.audible.com',
    'www.audible.com.au',
    'www.audible.de',
}


def equal(a: str, b: str) -> bool:
    if a == b:
        return True

    netloc = urlparse(a).netloc

    try:
        if netloc in STORES:
            return STORES[netloc].equal(a, b)
        elif netloc in PROCESSED:
            return PROCESSED[netloc].equal(a, b)

        warnings.warn(f'equal on unknown url: {a}')
    except Exception as e:
        warnings.warn(f'{a}, {b} equal error: {e}')
    return False


def hash_link(link: str) -> int:
    netloc = urlparse(link).netloc

    try:
        if netloc in STORES:
            return STORES[netloc].hash_link(link)
        elif netloc in PROCESSED:
            return PROCESSED[netloc].hash_link(link)

        warnings.warn(f'hash on unknown url: {link}')
    except Exception as e:
        warnings.warn(f'{link} hash error: {e}')
    return 0


def normalise(session: session.Session, link: str, resolve: bool = False) -> str | None:
    # normalise url, return None if failed
    netloc = urlparse(link).netloc

    if netloc in STORES:
        res = STORES[netloc].normalise(session, link)
        resolve &= netloc in RESOLVE
    elif netloc in PROCESSED:
        res = PROCESSED[netloc].normalise(session, link)
    elif netloc in IGNORE:
        res = ''
    else:
        res = None

    if resolve and res is None:
        new = session.resolve(link, force=True)
        if new != link:
            res = normalise(session, new, resolve=True)
    return res


def parse(session: session.Session, link: str, norm: str, force: bool = False, *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    netloc = urlparse(norm).netloc

    if netloc in STORES:
        store = STORES[netloc]
    elif netloc in PROCESSED:
        return None
    elif netloc not in IGNORE:
        warnings.warn(f'{netloc} parse not implemented')
        return None

    if store == amazon and not force:
        return None

    try:
        return store.parse(session, link, norm,
                           series=series,
                           publisher=publisher,
                           title=title,
                           index=index,
                           format=format,
                           isbn=isbn)
    except Exception as e:
        warnings.warn(f'{link}: {e}', RuntimeWarning)
    return None
