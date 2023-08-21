import datetime
import re
import warnings
from pathlib import Path
from random import random

from bs4 import BeautifulSoup, element
from utils import FORMATS, Info, Link, Series, Session, Table

NAME = 'Yen Press'

PAGES = Path('yen_press.csv')

TITLES = re.compile(r'https://yenpress\.com/titles/\d{13}-(?!.*(manga-vol|vol-\d+-manga|vol-\d+-comic|-chapter-\d+))[\w-]+')
LINK = re.compile(r'(https://yenpress.com)?/titles/(?P<isbn>\d{13})-(?P<name>[\w-]+)')


def parse(session: Session, link: str, links: dict[str, str]) -> None | tuple[Series, set[Info]]:
    page = session.get(link)
    if page.status_code == 404:
        return None
    soup = BeautifulSoup(page.content, 'html.parser')

    formats: list[str] = [x.text for x in soup.find(class_='tabs').find_all('span')]
    details: element.ResultSet[element.Tag] = soup.find(class_='book-details').find_all('div', recursive=False)
    series_title = details[0].select_one('span:-soup-contains("Series") + p').text
    title = soup.find('h1', class_='heading').text

    if (series_title.endswith('(light novel serial)')  # category of ebooks is inconsistent
        or (not soup.select_one('div.breadcrumbs > a[href="/category/light-novels"]')
            and details[0].select_one('span:-soup-contains("Imprint") + p').text != 'Yen On')):
        return None

    series = Series(None, series_title)
    info = set()
    for format, detail in zip(formats, details):
        if format not in FORMATS:
            continue

        isbn = detail.select_one('span:-soup-contains("ISBN") + p').text
        date = datetime.datetime.strptime(detail.select_one('span:-soup-contains("Release Date") + p').text,
                                          '%b %d, %Y').date()
        info.add(Info(series.key, links[isbn], NAME, NAME, title, 0, format, isbn, date))

    if info:
        return series, info
    return None


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Link)
    today = datetime.date.today()
    cutoff = today.replace(year=today.year - 1)
    # no date = not light novel
    skip = {row.link for row in pages if random() > 0.2 and (not row.date or row.date < cutoff)}

    isbns: dict[str, Series] = {inf.isbn: inf for inf in info}

    with Session() as session:
        page = session.get('https://yenpress.com/sitemap.xml')
        soup = BeautifulSoup(page.content, 'lxml-xml')

        links = {LINK.fullmatch(x.text).group('isbn'): x.text for x in soup.find_all('loc', string=TITLES)}
        for isbn, link in links.items():
            if isbn in skip:
                continue

            try:
                res = parse(session, link, links)
                if res:
                    series.add(res[0])
                    for inf in res[1]:
                        isbns[inf.isbn] = inf
                        date = inf.date
                        l = Link(inf.isbn, date)
                        pages.discard(l)
                        pages.add(l)
                        skip.add(inf.isbn)
                else:
                    l = Link(isbn, None)
                    pages.discard(l)
                    pages.add(l)
            except Exception as e:
                warnings.warn(f'{link}: {e}', RuntimeWarning)

    pages.save()
    return series, set(isbns.values())
