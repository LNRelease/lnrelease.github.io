import datetime
import re
import warnings
from random import random
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from session import Session
from utils import Info, Series, clean_str

NAME = 'BookWalker'

MOVE = re.compile(r'\$\w+\(\"(?P<id>[^\"]+)\",\"[^\"]+\"\)')
PUBLISHERS = {
    'Cross Infinite World': 'Cross Infinite World',
    'Dark Horse Comics': 'Dark Horse',
    'Graphic Audio': 'Dark Horse',
    'Denshobato': '',
    'Dreamscape Lore': 'J-Novel Club',
    'J-Novel Club': 'J-Novel Club',
    'Tantor Media, Inc': 'J-Novel Club',
    'Kodansha': 'Kodansha',
    'One Peace Books': 'One Peace Books',
    'One Peace Books (Audiobooks)': 'One Peace Books',
    'SB Creative': 'SB Creative',
    'Seven Seas Entertainment': 'Seven Seas Entertainment',
    'Tokyopop': '',
    'VIZ Media': 'VIZ Media',
    'Ize Press': '',
    'JY': 'Yen Press',
    'Yen Press': 'Yen Press',
}


def get_format(format: str, key: str) -> str:
    match format:
        case 'NOVEL':
            return 'Digital'
        case 'AUDIOBOOK':
            return 'Audiobook'
        case 'MANGA':
            return None
        case _:
            warnings.warn(f'Unknown format ({key}): {format}', RuntimeWarning)
            return None


def extract(soup: BeautifulSoup, selector: str) -> str:
    tag = soup.select_one(selector)
    if tag.text:
        return tag.text
    id = tag.find('template', attrs={}, id=True, recursive=False)['id']
    script = soup.select_one(rf'script:-soup-contains-own("\\22{id}\\22")')
    id = MOVE.fullmatch(script.text).group('id')
    res = soup.find(id=id).text
    if not res:
        link = soup.select_one('link[rel="canonical"]')['href']
        warnings.warn(f'({link}):\n{tag.prettify()}', RuntimeWarning)
    return res


def parse(session: Session, series: Series, link: str, index: int) -> Info | None:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'lxml')

    pub = extract(soup, 'div[aria-label="PUBLISHER"] > div[class$="__container"] > div > a[class$="__content"]')
    publisher = PUBLISHERS.get(pub)
    if publisher is None:
        warnings.warn(f'Unknown publisher: {pub}', RuntimeWarning)
    if not publisher:
        return None
    format = get_format(extract(soup, 'div[class$="__topSection"] div[aria-label="Format"]'), link)
    if not format:
        return None

    title = soup.select_one('meta[property="og:title"]')['content'].removesuffix(' [Dramatized Adaptation]')
    date = soup.select_one('p:-soup-contains-own("Released on")')
    date = datetime.datetime.strptime(date.text, 'Released on %b %d, %Y').date()
    info = Info(series.key, link, NAME, publisher, title, index, format, '', date)
    return info


def parse_series(session: Session, series: Series, url: str, skip: set[str]) -> set[Info]:
    info = set()

    page = session.get(url)
    soup = BeautifulSoup(page.content, 'lxml')
    if soup.select_one('div[class$="__totalWrapper"] + p').text != 'Volumes':
        return info

    lst = soup.select('a[class$="__bookCoverContainer"]')
    for index, a in enumerate(lst, start=1):
        link = urljoin(url, a['href'])
        try:
            title = a.next_sibling.select_one('div[class$="__content"] > div[class$="__title"] > a')['aria-label']
            if (title.startswith('BOOK☆WALKER Exclusive: ')
                or title.endswith(' [Bonus Item]')
                or ' Bundle Set]' in title
                    or link in skip):
                continue
            if inf := parse(session, series, link, index):
                info.add(inf)
        except Exception as e:
            warnings.warn(f'({link}): {e}', RuntimeWarning)

    return info


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=365)
    skip: set[str] = set()
    newest: dict[tuple[str, str], datetime.date] = {}
    for inf in info:
        if inf.date < cutoff and random() > 0.2:
            skip.add(inf.link)
        key = inf.serieskey, inf.format
        if inf.date > newest.setdefault(key, inf.date):
            newest[key] = inf.date

    params = {'formats[]': [2, 4], 'sort': 'updated'}
    with Session() as session:
        session.post('https://bookwalker.com/api/kyon/kyon.v1.UserService/Restrictions',
                     data=b'\x08\x01\x10\x01',  headers={'Content-Type': 'application/proto'})
        for i in range(1, limit):
            if i > 1:
                params['page'] = i
            try:
                page = session.get('https://bookwalker.com/browse', params=params)
                soup = BeautifulSoup(page.content, 'lxml')
                lst = soup.select('div[class$="__results"] > div[class$="__root"][class*="book-card-grid-view-module__"]'
                                  '> div[class$="__content"][class*="book-card-grid-view-module__"] > a')
                for a in lst:
                    title = a.text
                    if title[-12:].lower() == ' light novel':
                        title = title[-12:]
                    serie = Series(None, title)
                    format = a.previous_sibling.select_one('div[aria-label="Format"] > p').text
                    key = clean_str(a.text), get_format(format, title)
                    if newest.get(key, today) < cutoff and i > 2 and random() > 0.5:
                        continue
                    link = urljoin(page.url, a['href'])
                    if inf := parse_series(session, serie, link, skip):
                        series.add(serie)
                        info -= inf
                        info |= inf

                if not soup.select_one('a[href^="/browse?"]:has(> span[class$="__buttonInner"]'
                                       ' > span:-soup-contains-own("Next"))'):
                    break
            except Exception as e:
                warnings.warn(f'({i}): {e}', RuntimeWarning)
                break

    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 5)
