import datetime
import warnings
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from utils import Format, Info, Link, Series, Session, Table

NAME = 'VIZ Media'

PAGES = Path('viz.csv')


def parse(session: Session, link: str) -> tuple[Series, Info] | None:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'html.parser')

    series_title = soup.find('strong', string='Series').find_next('a').text
    title = soup.select_one('div#purchase_links_block h2').text
    index = 0
    formats = {x.text for x in soup.find(role='tablist').find_all('a')}
    if any(x in formats for x in ('Paperback', 'Hardback', 'Hardcover')):
        if 'Digital' in formats:
            format = Format.PHYSICAL_DIGITAL
        else:
            format = Format.PHYSICAL
    elif 'Digital' in formats:
        format = Format.DIGITAL
    else:
        warnings.warn(f'{link} unknown format', RuntimeWarning)
        format = Format.NONE
    isbn = soup.find('strong', string='ISBN-13').next_sibling.strip()
    date = soup.find('strong', string='Release').next_sibling.strip()
    date = datetime.datetime.strptime(date, '%B %d, %Y').date()

    series = Series(None, series_title)
    info = Info(series.key, link, NAME, NAME, title, index, format, isbn, date)
    return series, info


def scrape_full(limit: int = 1000) -> tuple[set[Series], set[Info]]:
    limit += 1
    pages = Table(PAGES, Link)
    today = datetime.date.today()
    cutoff = today.replace(year=today.year - 1)
    # no date = not light novel
    skip = {row.link for row in pages.rows if not row.date or row.date < cutoff}

    series = set()
    info = set()

    with Session() as session:
        site = r'https://www.viz.com/search/{}?search=Novel&category=Novel'
        for i in range(1, limit):
            page = session.get(site.format(i))
            soup = BeautifulSoup(page.content, 'html.parser')

            results = soup.select('div#results > article > div > a')
            for a in results:
                link = urljoin('https://www.viz.com', a.get('href'))
                if link in skip:
                    continue

                try:
                    res = parse(session, link)
                    if res:
                        series.add(res[0])
                        info.add(res[1])
                        date = res[1].date
                    else:
                        date = None
                    pages.add(Link(link, date))
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

            if not results:
                break
    # pages.save()
    return series, info


def scrape() -> tuple[set[Series], set[Info]]:
    return scrape_full(5)
