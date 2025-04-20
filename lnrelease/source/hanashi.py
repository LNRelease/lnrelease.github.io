import datetime
import re
import warnings
from collections import defaultdict
from pathlib import Path
from random import random
from urllib.parse import quote, urlparse

import store
from bs4 import BeautifulSoup, element
from session import Session
from utils import Info, Key, Series, Table

NAME = 'Hanashi Media'

PAGES = Path('hanashi.csv')

TITLE = re.compile(r'(?P<title>.+) – Hanashi Media')
STORE = re.compile(r'[Gg]et at .+')
ISBN = re.compile(r'^.*ISBN:\s*(?:(?P<isbn>[\d-]{13,})|Not Yet|)$')
VOLUME = re.compile(r'Volume (?P<volume>\d+(?:\.\d)?)')


def parse(session: Session, link: str, skip: set[str]) -> tuple[Series, set[Info]]:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'lxml')
    series_title = TITLE.fullmatch(soup.title.text).group('title')
    series = Series(None, series_title)
    info = set()
    isbns: defaultdict[tuple[int, element.NavigableString], dict[str, list[str]]] = defaultdict(dict)

    for button in soup.find_all(string=STORE):
        a = button.find_parent('a')
        isbn = a.find_previous(string=ISBN)
        if not isbn:
            warnings.warn(f'No ISBN found: {link}', RuntimeWarning)
            continue

        url: str = a.get('href')
        if url[-1] == '#' or not urlparse(url).scheme:
            continue
        url = session.resolve(url.strip())

        if norm := store.normalise(session, url, resolve=True):
            isbns[(id(isbn), isbn)].setdefault(norm, [norm]).append(url)
        elif norm is None:
            warnings.warn(f'{url} normalise failed', RuntimeWarning)

    u = urlparse(link)
    for index, ((_, isbn), urls) in enumerate(isbns.items(), start=1):
        if ((parent := isbn.find_parent('div', class_='elementor-element'))
            and (prev := parent.find_previous_sibling('div', class_='elementor-element'))
            and (h3 := prev.find('h3'))
                and (match := VOLUME.fullmatch(h3.text))):
            volume = match.group('volume').lstrip('0')
            title = f'{series_title} Volume {volume}'
            u = u._replace(fragment=f':~:text={quote(match.group(0))}')
        elif len(isbns) == 1:
            title = f'{series_title} Volume 1'
        else:
            title = f'{series_title} Volume {index}'
            u = u._replace(fragment=quote(f'Volume {index:02d}'))

        isbn = ISBN.fullmatch(isbn.parent.text).group('isbn') or ''
        alts = []
        force = True
        for norm, links in sorted(urls.items(), key=lambda x: 'amazon.' in x[0]):
            if urlparse(norm).netloc in store.PROCESSED:
                alts.append(norm)
            else:
                res = store.parse(session, links,
                                  (force or random() < 0.1) and norm not in skip,
                                  series=series, publisher=NAME,
                                  title=title, index=index,
                                  format='Digital', isbn=isbn)
                if res and res[1]:
                    info |= res[1]
                    force = False
                    alts.extend(inf.link for inf in res[1])
                else:
                    alts.append(norm)

        info.add(Info(series.key, u.geturl(), NAME, NAME, title, index, 'Digital', isbn, None, alts))

    return series, info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Key)
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=30)
    skip = {row.key for row in pages if random() > 0.1 and row.date < cutoff}

    with Session() as session:
        page = session.get('https://hanashi.media/')
        soup = BeautifulSoup(page.content, 'lxml')
        links = (a.get('href') for a in soup
                 .find(class_='menu-label', string='Light Novels')
                 .find_parent('li').ul.find_all('a'))
        for link in links:
            try:
                res = parse(session, link, skip)

                if len(res[1]) > 0:
                    series.add(res[0])
                    info -= {i for i in info if i.serieskey == res[0].key}
                    info |= res[1]
                    for inf in res[1]:
                        if inf.source == NAME:
                            continue
                        l = Key(inf.link, inf.date)
                        pages.discard(l)
                        pages.add(l)
            except Exception as e:
                warnings.warn(f'({link}): {e}', RuntimeWarning)

    pages.save()
    return series, info
