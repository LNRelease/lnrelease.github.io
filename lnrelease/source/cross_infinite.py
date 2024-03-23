import datetime
import warnings
from collections import defaultdict
from urllib.parse import urljoin, urlparse

import store
from bs4 import BeautifulSoup
from session import Session
from utils import Info, Series, find_series

NAME = 'Cross Infinite World'


def get_format(s: str) -> str:
    match s:
        case ('Paperback'
              | 'Print'
              | 'Paperback Releases'
              | 'Print Releases'):
            return 'Paperback'
        case ('Hardcover'
              | 'Hardcover Releases'):
            return 'Hardcover'
        case ('Audiobook'
              | 'Audiobook Release'):
            return 'Audiobook'
        case ('Digital'
              | 'Digital Releases'
              | 'Digital Release'
              | 'Available Now!'
              | 'Pre-Order Now!'):
            return 'Digital'
        case _:
            warnings.warn(f'Unknown CIW format: {s}', RuntimeWarning)
            return 'Digital'


def parse(session: Session, link: str) -> tuple[Series, set[Info]]:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'lxml')
    h2 = soup.select_one('div.container > div.row + div.row > div.box > h2 > strong')
    series_title = h2.text.removesuffix(' Volumes')
    series = Series(None, series_title)
    info = set()

    for index, panel in enumerate(soup.find_all('div', class_='panel'), start=1):
        if a := panel.find('a', recursive=False):
            link = urljoin('https://crossinfworld.com/', a.get('href'))
        title = panel.find('div', class_='panel-heading').strong.text

        links: defaultdict[str, dict[str, str]] = defaultdict(dict)
        for a in panel.find_all('a'):
            url: str = a.get('href').strip()
            u = urlparse(url)
            if not u.scheme or u.netloc == 'crossinfworld.com':
                continue
            url = session.resolve(url)

            format = get_format(a.find_previous('p').text)
            norm = store.normalise(session, url, resolve=True)
            if norm is None:
                warnings.warn(f'{url} normalise failed')
            elif norm and (norm not in links[format]
                           or u.netloc == urlparse(norm).netloc):
                links[format][norm] = url

        for format, urls in links.items():
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
                                      title=title, index=index, format=format)
                    if res and res[1]:
                        info |= res[1]
                        force = False
                        alts.extend(inf.link for inf in res[1])
                    else:
                        alts.append(norm)

            info.add(Info(series.key, link, NAME, NAME, title, index, format, '', None, alts))

    return series, info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    items = {(inf.link, inf.format): inf for inf in info}
    with Session() as session:
        page = session.get(r'https://crossinfworld.com/series.html')
        soup = BeautifulSoup(page.content, 'lxml')
        for a in soup.select('div.row > div.box > div > a'):
            try:
                link = urljoin('https://crossinfworld.com/', a.get('href'))
                res = parse(session, link)

                if len(res[1]) > 0:
                    series.add(res[0])
                    for inf in res[1]:
                        key = inf.link, inf.format
                        if inf.source == NAME and key in items:
                            inf.isbn = items[key].isbn
                            inf.date = items[key].date
                        items[key] = inf

            except Exception as e:
                warnings.warn(f'{link}: {e}', RuntimeWarning)

        page = session.get(r'https://crossinfworld.com/Calendar.html')
        soup = BeautifulSoup(page.content, 'lxml')
        for book in soup.select('table#sort > tbody > tr'):
            format = get_format(book.find('td', {'data-table-header': 'Format'}).text)
            a = book.find('td', {'data-table-header': 'Title'}).a
            title = a.text
            link = urljoin('https://crossinfworld.com/', a.get('href'))
            date = book.find('td', {'data-table-header': 'Date'}).text
            date = datetime.datetime.strptime(date, '%m/%d/%y').date()
            isbn = book.find('td', {'data-table-header': 'ISBN'}).text

            key = link, format
            if key in items:
                items[key].isbn = isbn
                items[key].date = date
            else:
                warnings.warn(f'{title} ({format}) not found: {link}', RuntimeWarning)
                serie = find_series(title, series) or Series(None, title)
                series.add(serie)
                items[key] = Info(serie.key, link, NAME, NAME, title, 0, format, isbn, date)

    return series, set(items.values())
