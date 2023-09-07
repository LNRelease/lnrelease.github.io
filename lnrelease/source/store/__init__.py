import warnings
from urllib.parse import urlparse

from utils import Info, Series

from . import (amazon, apple, audible, barnes_noble, book_walker, google, kobo,
               right_stuf)

STORES = {
    'www.amazon.ca': amazon,
    'www.amazon.co.uk': amazon,
    'www.amazon.com': amazon,
    'www.amazon.com.au': amazon,
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
    'www.rightstufanime.com': right_stuf,
}

IGNORE = {
    'www.amazon.de',
    'www.amazon.co.jp',
    'www.bookdepository.com',
    'www.booksamillion.com',
    'bookshop.org',
    'books.google.com',
    'gum.co',
    'gumroad.com',
    'www.indiebound.org',
    'www.powells.com',
    'www.walmart.com',
}


def normalise(session, link: str) -> str | None:
    # normalise url return None if failed
    netloc = urlparse(link).netloc
    link = session.resolve(link)
    netloc = urlparse(link).netloc

    if 'audible' in netloc:
        return audible.normalise(link)
    elif netloc in STORES:
        return STORES[netloc].normalise(link)
    elif netloc in PROCESSED:
        return PROCESSED[netloc].normalise(link)
    elif netloc not in IGNORE:
        None
    return ''


def parse(session, link: str, norm: str, force: bool = False, *,
          series: Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = '') -> tuple[Series, set[Info]] | None:
    netloc = urlparse(link).netloc

    if 'audible' in netloc:
        store = audible
    elif netloc in STORES:
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
