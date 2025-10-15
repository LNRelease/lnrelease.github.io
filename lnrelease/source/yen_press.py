import datetime
import re
import warnings
from pathlib import Path
from random import random

from bs4 import BeautifulSoup, element
from session import Session
from utils import FORMATS, Info, Key, Series, Table

NAME = 'Yen Press'

PAGES = Path('yen_press.csv')

TITLES = re.compile(r'https://yenpress\.com/titles/\d{13}-(?!.*(manga-vol|vol-\d+-manga|vol-\d+-comic|-chapter-\d+))[\w-]+')
LINK = re.compile(r'(https://yenpress.com)?/titles/(?P<isbn>\d{13})-(?P<name>[\w-]+)')
OMNIBUS = re.compile(r'contains(?: the complete)? volumes (?P<volume>\d+(?:\.\d)?-\d+(?:\.\d)?)', flags=re.IGNORECASE)
START = re.compile(r'(?P<start>.+?) (?:omnibus |collector\'s edition |volume )+\d+(?: \(light novel\))?', flags=re.IGNORECASE)


def parse(session: Session, link: str, links: dict[str, str]) -> None | tuple[Series, set[Info]]:
    page = session.get(link)
    if page is None or page.status_code == 404:
        return None
    soup = BeautifulSoup(page.content, 'lxml')

    formats: list[str] = [x.text for x in soup.select('.tabs > span')]
    details: element.ResultSet[element.Tag] = soup.select('.book-details > div')
    if not formats or not details:
        return None
    series_title = details[0].select_one('span:-soup-contains("Series") + p').text
    if series_title.endswith('(light novel serial)'):
        return None

    category = soup.select_one('div.breadcrumbs.desktop-only > a:last-child').get('href')
    imprint = details[0].select_one('span:-soup-contains("Imprint") + p').text
    # category of ebooks is inconsistent
    if (category != '/category/light-novels' and category != '/category/audio-books'
            and imprint != 'Yen On' and imprint != 'Yen Audio'):
        return None

    title = soup.select_one('h1.heading').text
    if ((desc := soup.select_one('.book-info > .content-heading-txt'))
            and (vol := OMNIBUS.search(desc.text))
            and (start := START.fullmatch(title))):  # rename omnibus volume
        title = f'{start.group("start")} Volume {vol.group("volume")}'
    series = Series(None, series_title)
    info = set()
    publisher = imprint if imprint == 'J-Novel Club' else NAME
    for format, detail in zip(formats, details):
        if format not in FORMATS:
            continue

        isbn = detail.select_one('span:-soup-contains("ISBN") + p').text
        date = datetime.datetime.strptime(detail.select_one('span:-soup-contains("Release Date") + p').text,
                                          '%b %d, %Y').date()
        info.add(Info(series.key, links[isbn], NAME, publisher, title, 0, format, isbn, date))

    if info:
        return series, info
    return None


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Key)
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=180)
    # no date = not light novel
    skip = {row.key for row in pages if random() > 0.2 and (not row.date or row.date < cutoff)}

    isbns: dict[str, Info] = {inf.isbn: inf for inf in info}

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
                        l = Key(inf.isbn, date)
                        pages.discard(l)
                        pages.add(l)
                        skip.add(inf.isbn)
                elif isbn not in isbns:
                    l = Key(isbn, None)
                    pages.discard(l)
                    pages.add(l)
            except Exception as e:
                warnings.warn(f'({link}): {e}', RuntimeWarning)

    pages.save()
    return series, set(isbns.values())
