import re
import warnings
from collections import defaultdict
from urllib.parse import quote, urlparse

import store
from bs4 import BeautifulSoup, element
from session import Session
from utils import Info, Series

NAME = 'Hanashi Media'

TITLE = re.compile(r'(?P<title>.+) – Hanashi Media')
STORE = re.compile(r'[Gg]et at .+')
ISBN = re.compile(r'^.*ISBN:\s*(?:(?P<isbn>[\d-]{13,})|Not Yet|)$')
VOLUME = re.compile(r'Volume (?P<volume>\d+(?:\.\d)?)')


def parse(session: Session, link: str) -> tuple[Series, set[Info]]:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'lxml')
    series_title = TITLE.fullmatch(soup.title.text).group('title')
    series = Series(None, series_title)
    info = set()
    isbns: defaultdict[element.NavigableString, dict[str, str]] = defaultdict(dict)

    for button in soup.find_all(string=STORE):
        a = button.find_parent('a')
        isbn = a.find_previous(string=ISBN)
        if not isbn:
            warnings.warn(f'No ISBN found: {link}', RuntimeWarning)
            continue

        url: str = a.get('href')
        u = urlparse(url)
        if not u.scheme:
            continue
        url = session.resolve(url.strip())

        norm = store.normalise(session, url, resolve=True)
        if norm is None:
            warnings.warn(f'{url} normalise failed', RuntimeWarning)
        elif norm and (norm not in isbns[isbn]
                       or u.netloc == urlparse(norm).netloc):
            isbns[isbn][norm] = url

    u = urlparse(link)
    for index, (isbn, urls) in enumerate(isbns.items(), start=1):
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
            warnings.warn(f'No volume found: {link}', RuntimeWarning)
            title = f'{series_title} Volume {index}'
            u = u._replace(fragment=str(index))

        isbn = ISBN.fullmatch(isbn.parent.text).group('isbn') or ''
        alts = []
        force = True  # leave amazon to last, force only if no other sources
        for norm, url in sorted(urls.items(), key=lambda x: 'amazon' in x[0]):
            netloc = urlparse(norm).netloc
            if netloc in store.PROCESSED:
                alts.append(norm)
                force = False
            else:
                res = store.parse(session, url, norm, force,
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
    with Session() as session:
        page = session.get(r'https://hanashi.media/')
        soup = BeautifulSoup(page.content, 'lxml')
        links = (a.get('href') for a in soup
                 .find(class_='menu-label', string='Light Novels')
                 .find_parent('li').ul.find_all('a'))
        for link in links:
            try:
                res = parse(session, link)

                if len(res[1]) > 0:
                    series.add(res[0])
                    info -= res[1]
                    info |= res[1]
            except Exception as e:
                warnings.warn(f'{link}: {e}', RuntimeWarning)

    return series, info
