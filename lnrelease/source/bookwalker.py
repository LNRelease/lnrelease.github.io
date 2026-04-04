import datetime
import re
import warnings
from random import random
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from session import Session
from store.bookwalker import PATH
from utils import Info, Series, clean_str

NAME = 'BookWalker'

HYDRATE = re.compile(r'^\$RS\(\"(?P<src>S:\w+)\",\"(?P<dst>P:\w+)\"\)$')
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


def get_soup(session: Session, link: str, **kwargs) -> BeautifulSoup:
    page = session.get(link, **kwargs)
    soup = BeautifulSoup(page.content, 'lxml')
    for script in soup.find_all('script', string=HYDRATE):
        match = HYDRATE.fullmatch(script.text)
        dst = soup.find(id=match.group('dst'))
        src = soup.find(id=match.group('src'))
        dst.insert_before(*src.contents)
        src.extract()
        dst.extract()
    return soup


def get_id(link: str) -> str:
    return PATH.fullmatch(urlparse(link).path).group('id')


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


def parse(session: Session, series: Series, link: str, index: int) -> Info | None:
    soup = get_soup(session, link)
    pub = soup.select_one('div[aria-label="PUBLISHER"] > div[class$="__container"] > div > a[class$="__content"]')
    publisher = PUBLISHERS.get(pub.text)
    if publisher is None:
        warnings.warn(f'Unknown publisher: {pub.text}', RuntimeWarning)
    if not publisher:
        return None
    format = soup.select_one('div[class$="__topSection"] div[aria-label="Format"]')
    format = get_format(format.text, link)
    if not format:
        return None

    title = soup.select_one('meta[property="og:title"]')['content'].removesuffix(' [Dramatized Adaptation]')
    date = soup.select_one('p:-soup-contains-own("Released on")')
    date = datetime.datetime.strptime(date.text, 'Released on %b %d, %Y').date()
    info = Info(series.key, link, NAME, publisher, title, index, format, '', date)
    return info


def parse_series(session: Session, series: Series, uids: dict[str, Info], url: str, skip: set[str]) -> None:
    try:
        soup = get_soup(session, url)
        if soup.select_one('div[class$="__totalWrapper"] + p').text != 'Volumes':
            return
    except Exception as e:
        warnings.warn(f'({url}): {e}', RuntimeWarning)
        return

    lst = soup.select('a[class$="__bookCoverContainer"]')
    for index, a in enumerate(lst, start=1):
        link = urljoin(url, a['href'])
        try:
            uid = get_id(link)
            title = a.next_sibling.select_one('div[class$="__title"] > a')['aria-label']
            if (title.startswith('BOOK☆WALKER Exclusive: ')
                or title.endswith(' [Bonus Item]')
                or ' Bundle Set]' in title
                    or link in skip):
                if uid in uids:
                    inf = uids[uid]
                    inf.serieskey = series.key
                    inf.link = link
                    inf.index = index
                continue
            if inf := parse(session, series, link, index):
                uids[uid] = inf
        except Exception as e:
            warnings.warn(f'({link}): {e}', RuntimeWarning)


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=180)
    skip: set[str] = set()
    newest: dict[tuple[str, str], datetime.date] = {}
    for inf in info:
        if inf.date < cutoff and random() > 0.2:
            skip.add(inf.link)
        key = inf.serieskey, inf.format
        if inf.date > newest.setdefault(key, inf.date):
            newest[key] = inf.date
    uids = {get_id(inf.link): inf for inf in info}

    params = {'formats[]': [2, 4], 'sort': 'updated'}
    with Session() as session:
        session.post('https://bookwalker.com/api/kyon/kyon.v1.UserService/Restrictions',
                     data=b'\x08\x01\x10\x01',  headers={'Content-Type': 'application/proto'})
        for i in range(1, limit):
            if i > 1:
                params['page'] = i
            finish = True
            try:
                soup = get_soup(session, 'https://bookwalker.com/browse', params=params)
                finish = soup.select_one('a[href^="/browse?"]:has(> span[class$="__buttonInner"]'
                                         ' > span:-soup-contains-own("Next"))') is None
                lst = soup.select('div[class$="__results"] > div[class$="__root"][class*="book-card-grid-view-module__"]'
                                  '> div[class$="__content"][class*="book-card-grid-view-module__"] > a')
                for a in lst:
                    title = a.text
                    if title[-12:].lower() == ' light novel':
                        title = title[:-12]
                    serie = Series(None, title)
                    format = a.previous_sibling.select_one('div[aria-label="Format"] > p').text
                    key = clean_str(a.text), get_format(format, title)
                    if newest.get(key, today) < cutoff and i > 2 and random() > 0.5:
                        continue

                    link = urljoin('https://bookwalker.com/', a['href'])
                    parse_series(session, serie, uids, link, skip)

            except Exception as e:
                warnings.warn(f'({i}): {e}', RuntimeWarning)
            if finish:
                break

    return series, set(uids.values())


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 5)
