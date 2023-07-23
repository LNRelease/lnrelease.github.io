import datetime
import warnings
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from utils import Info, Link, Series, Session, Table

NAME = 'VIZ Media'

PAGES = Path('viz.csv')


def parse(session: Session, link: str) -> tuple[Series, set[Info], datetime.date] | None:
    info = set()
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'html.parser')

    series_title = soup.find('strong', string='Series').find_next('a').text
    title = soup.select_one('div#purchase_links_block h2').text
    index = 0
    isbn = soup.find('strong', string='ISBN-13').next_sibling.strip()
    date = soup.find('strong', string='Release').next_sibling.strip()
    date = datetime.datetime.strptime(date, '%B %d, %Y').date()

    series = Series(None, series_title)
    for a in soup.find(role='tablist').find_all('a'):
        format = a.text
        url = f'{link}/{format.lower()}'
        info.add(Info(series.key, url, NAME, NAME, title, index, format, isbn, date))
    return series, info, date


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    limit += 1
    pages = Table(PAGES, Link)
    today = datetime.date.today()
    cutoff = today.replace(year=today.year - 1)
    # no date = not light novel
    skip = {row.link for row in pages if not row.date or row.date < cutoff}

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
                        info |= res[1]
                        date = res[2]
                    else:
                        date = None
                    pages.replace(Link(link, date))
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

            if not results:
                break
    pages.save()
    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 5)
