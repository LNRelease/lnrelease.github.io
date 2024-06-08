import datetime
import re
import warnings
from pathlib import Path
from random import random
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from session import Session
from utils import Info, Key, Series, Table

NAME = 'VIZ Media'

PAGES = Path('viz.csv')
ISBN = re.compile(r'e?ISBN-13')


def parse(session: Session, link: str) -> tuple[Series, set[Info], datetime.date] | None:
    info = set()
    page = session.get(link, web_cache=True)
    soup = BeautifulSoup(page.content, 'lxml')

    series_title = soup.find('strong', string='Series').find_next('a').text
    title = soup.select_one('div#purchase_links_block h2').text
    index = 0
    isbn = soup.find('strong', string=ISBN).next_sibling.strip()
    date = soup.find('strong', string='Release').next_sibling.strip()
    date = datetime.datetime.strptime(date, '%B %d, %Y').date()

    series = Series(None, series_title)
    for a in soup.find(role='tablist').find_all('a'):
        format = a.text
        url = f'{link}/{format.lower()}'
        i = isbn if a.get('data-tab-state') == 'on' else ''
        info.add(Info(series.key, url, NAME, NAME, title, index, format, i, date))
    return series, info, date


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Key)
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=365)
    # no date = not light novel
    skip = {row.key for row in pages if random() > 0.2 and (not row.date or row.date < cutoff)}

    with Session() as session:
        site = 'https://www.viz.com/search/{}?search=Novel&category=Novel'
        for i in range(1, limit + 1):
            page = session.get(site.format(i))
            soup = BeautifulSoup(page.content, 'lxml')

            results = soup.select('div#results > article > div > a')
            for a in results:
                link = urljoin('https://www.viz.com/', a.get('href'))
                if link in skip:
                    continue

                try:
                    res = parse(session, link)
                    if res:
                        series.add(res[0])
                        info -= res[1]
                        info |= res[1]
                        date = res[2]
                    else:
                        date = None
                    l = Key(link, date)
                    pages.discard(l)
                    pages.add(l)
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

            if not results:
                break
    pages.save()
    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 5)
