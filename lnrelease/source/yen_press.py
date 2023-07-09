import datetime
import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup
from utils import Format, Info, Link, Series, Session, Table

NAME = 'Yen Press'

PAGES = Path('yen_press.csv')

TITLES = re.compile(r'https://yenpress\.com/titles/\d{13}-(?!.*(manga-vol|vol-\d+-manga|vol-\d+-comic|-chapter-\d+))[\w-]+')
LINK = re.compile(r'(https://yenpress.com)?/titles/(?P<isbn>\d{13})-(?P<name>[\w-]+)')


def parse(session: Session, link: str, isbn: str) -> None | tuple[Series, Info]:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'html.parser')

    details = soup.find(class_='book-details')
    # category of ebooks is inconsistent
    if (not soup.select_one('div.breadcrumbs > a[href="/category/light-novels"]')
            and details.select_one('span:-soup-contains("Imprint") + p').text != 'Yen On'):
        return None

    series_title = details.select_one('span:-soup-contains("Series") + p').text
    if series_title.endswith('(light novel serial)'):
        return None

    title = soup.find('h1', class_='heading').text
    date = datetime.datetime.strptime(details.select_one('span:-soup-contains("Release Date") + p').text,
                                      '%b %d, %Y').date()
    match soup.find(class_='deliver active').text:
        case 'Paperback' | 'Hardback':
            format = Format.PHYSICAL
        case 'Digital':
            format = Format.DIGITAL
        case _:
            format = None
            warnings.warn(f'{link} unknown format', RuntimeWarning)
    series = Series(None, series_title)
    info = Info(series.key, link, NAME, NAME, title, 0, format, isbn, date)
    return series, info


def scrape_full() -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Link)
    today = datetime.date.today()
    cutoff = today.replace(year=today.year - 1)
    # no date = not light novel
    skip = {row.link for row in pages.rows if not row.date or row.date < cutoff}

    series: set[Series] = set()
    # keep only smallest isbn on latest date of same title/format
    info: dict[tuple[str, Format], Info] = {}

    with Session() as session:
        page = session.get('https://yenpress.com/sitemap.xml')
        soup = BeautifulSoup(page.content, 'lxml-xml')

        for link in soup.find_all('loc', string=TITLES):
            link = link.text
            if link in skip:
                continue
            isbn = LINK.fullmatch(link).group('isbn')

            try:
                res = parse(session, link, isbn)
                if res:
                    serie = res[0]
                    inf = res[1]

                    key = (inf.title, inf.format)
                    if (key not in info or inf.date > info[key].date
                            or inf.date == info[key].date and inf.isbn < info[key].isbn):
                        series.add(serie)
                        info[key] = inf
                    date = inf.date
                else:
                    date = None
                pages.add(Link(link, date))
            except Exception as e:
                warnings.warn(f'{link}: {e}', RuntimeWarning)

    pages.save()
    return series, set(info.values())
