import datetime
import re
import warnings
from pathlib import Path
from random import random
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
from session import Session
from utils import EPOCH, Info, Key, Series, Table

NAME = 'BookWalker'

PAGES = Path('bookwalker.csv')
HYDRATE = re.compile(r'(?:^|;)\$R(?P<t>[SC])\(\"(?P<a>[SB]:\w+)\",\"(?P<b>[PS]:\w+)\"\)$')
PATH = re.compile(r'/(?:volume|chapter|series)/(?P<id>[A-Z\d]{12})/[\w-]+')
PUBLISHERS = {
    'Cross Infinite World': 'Cross Infinite World',
    'Crossed Hearts': '',
    'Dark Horse Comics': 'Dark Horse',
    'Graphic Audio': 'Dark Horse',
    'Denshobato': '',
    'Dreamscape Lore': 'J-Novel Club',
    'J-Novel Club': 'J-Novel Club',
    'JNC Audio': 'J-Novel Club',
    'Tantor Media': 'J-Novel Club',
    'Kodansha': 'Kodansha',
    'One Peace Books': 'One Peace Books',
    'One Peace Books (Audiobooks)': 'One Peace Books',
    'SB Creative': 'SB Creative',
    'Seven Seas Entertainment': 'Seven Seas Entertainment',
    'Seven Seas Siren': 'Seven Seas Entertainment',
    'Tokyopop': '',
    'VIZ Media': 'VIZ Media',
    'Ize Press': '',
    'JY': 'Yen Press',
    'Yen Press': 'Yen Press',
}


def get_soup(session: Session, link: str, **kwargs) -> BeautifulSoup:
    page = session.get(link, **kwargs)
    soup = BeautifulSoup(page.content, 'lxml')
    if redirect := soup.find('meta', attrs={'http-equiv': 'refresh', 'id': '__next-page-redirect'}):
        link = urljoin(page.url, redirect['content'].split('url=')[-1])
        return get_soup(session, link, **kwargs)
    for script in soup.find_all('script'):
        for t, a, b in HYDRATE.findall(script.text):
            match t:
                case 'S':
                    src = soup.find(id=a)
                    dst = soup.find(id=b)
                case 'C':
                    dst = soup.find(id=a)
                    src = soup.find(id=b)
                    while dst and dst != '/$':
                        nxt = dst.next_sibling
                        dst.extract()
                        dst = nxt
            if dst is not None and src is not None:
                dst.insert_before(*src.contents)
            src.extract()
            dst.extract()
        script.extract()
    return soup


def get_id(link: str) -> str:
    return PATH.fullmatch(urlparse(link).path).group('id')


def get_format(format: str, key: str) -> str | None:
    match format:
        case 'NOVEL':
            return 'Digital'
        case 'AUDIOBOOK':
            return 'Audiobook'
        case 'MANGA' | 'WEBTOON':
            return None
        case _:
            warnings.warn(f'Unknown format ({key}): {format}', RuntimeWarning)
            return None


def parse(soup: BeautifulSoup, link: str, series: Series = None, index: int = 0) -> tuple[Series, Info] | None:
    pub = soup.select_one('p:-soup-contains-own(PUBLISHER) ~ p')
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
    if date := soup.select_one('p:-soup-contains-own("Publication Date") ~ p'):
        date = datetime.datetime.strptime(date.text[:-4], '%b %d, %Y').date()
    else:
        warnings.warn(f'No date found: {link}', RuntimeWarning)
        return None
    if series is None:
        series = Series(None, soup.select_one('p:-soup-contains-own(SERIES) ~ p').text)
    isbn = ''
    if tag := soup.select_one('p:-soup-contains-own(ISBN) ~ p'):
        isbn = tag.text
    info = Info(series.key, link, NAME, publisher, title, index, format, isbn, date)
    return series, info


def parse_series(session: Session, uids: dict[str, Info], url: str, new: bool = True
                 ) -> tuple[Series, dict[str, Info]] | Series | None:
    soup = get_soup(session, url)
    if soup.select_one('div[class$="__totalWrapper"] + p').text != 'Volumes':
        return None
    format = soup.select_one('div[class$="__topSection"] div[aria-label="Format"]')
    if not get_format(format.text, url):
        return None
    series = Series(None, soup.select_one('[class$="__title-page"]').text)
    info = {}

    lst = soup.select('a[class$="__bookCoverContainer"]')
    for index, a in enumerate(lst, start=1):
        link = urljoin(url, a['href'])
        try:
            uid = get_id(link)
            title = a.next_sibling.select_one('div[class$="__title"] > a')['aria-label']
            if (not new
                or title.startswith('BOOK☆WALKER Exclusive: ')
                or title.endswith(' [Bonus Item]')
                    or ' Bundle Set]' in title):
                if inf := uids.get(uid):
                    inf.serieskey = series.key
                    inf.link = link
                    inf.index = index
            elif res := parse(get_soup(session, link), link, series, index):
                info[uid] = res[1]

        except Exception as e:
            warnings.warn(f'({link}): {e}', RuntimeWarning)
    if not new:
        return series
    return series, info


def parse_month(session: Session, url: str, uids: dict[str, Info], new: dict[str, Info], series: set[Series],
                pages: Table[Key], keys: dict[str, datetime.date], key: str) -> BeautifulSoup:
    try:
        soup = get_soup(session, url)
        for group in soup.select('div[class$="__groups"] > div[class$="__group"]'):
            date = group.select_one('div[class$="__groupDateHeader"] h2')
            date = datetime.datetime.strptime(date.text, '%b %d, %Y').date()
            for entry in group.select('ul[class$="__entryList"] > li[class$="__entry"] a'):
                try:
                    link = urljoin(url, entry['href'])
                    uid = get_id(link)
                    if inf := uids.get(uid):
                        inf.date = date
                        continue
                    elif uid in keys:
                        continue

                    s = get_soup(session, link)
                    if res := parse(s, link):
                        new[uid] = res[1]
                        uids[uid] = res[1]
                        slink = urljoin(link, s.select_one('p:-soup-contains-own(SERIES) ~ p > a')['href'])
                        series.add(parse_series(session, uids, slink, new=False) or res[0])
                        if not keys.get(slink):
                            k = Key(get_id(slink), EPOCH)
                            pages.discard(k)
                            pages.add(k)
                    else:
                        new[uid] = None

                except Exception as e:
                    warnings.warn(f'({link}): {e}', RuntimeWarning)
        return soup

    except Exception as e:
        warnings.warn(f'{key}: {e}', RuntimeWarning)


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Key)
    keys = {row.key: row.date for row in pages}
    today = datetime.date.today()
    uids = {get_id(inf.link): inf for inf in info}

    with Session() as session:
        session.post('https://bookwalker.com/api/kyon/kyon.v1.UserService/Restrictions',
                     data=b'\x08\x01\x10\x01',  headers={'Content-Type': 'application/proto'})
        sitemap = session.get('https://bookwalker.com/sitemap.xml')
        soup = BeautifulSoup(sitemap.content, 'lxml-xml')

        new = {}
        for loc in soup.select('sitemap > loc:-soup-contains("/series_")'):
            page = session.get(loc.text)
            for url in BeautifulSoup(page.content, 'lxml-xml').select('urlset > url'):
                try:
                    link = url.loc.text
                    uid = get_id(link)
                    lastmod = datetime.datetime.fromisoformat(url.lastmod.text).date()
                    date = keys.get(uid, EPOCH)
                    if date is None or date >= lastmod and random() > 0.1:
                        continue
                    elif res := parse_series(session, uids, link):
                        if res[1]:
                            series.add(res[0])
                            new |= res[1]
                        k = Key(uid, lastmod)
                        pages.discard(k)
                        pages.add(k)
                        keys[uid] = lastmod
                    else:
                        k = Key(uid, None)
                        pages.discard(k)
                        pages.add(k)
                        keys[uid] = None
                except Exception as e:
                    warnings.warn(f'({link}): {e}', RuntimeWarning)

        uids |= new
        link = 'https://bookwalker.com/calendar?' + urlencode({'formats[]': [2, 4], 'type': 'volume'}, doseq=True)
        s = parse_month(session, link, uids, new, series, pages, keys, 'now')
        for tab in s.select('div[class$="__tabBar"] > a[class$="__tab"]'):
            link = urljoin('https://bookwalker.com', tab['href'])
            parse_month(session, link, uids, new, series, pages, keys, link[-6:])

        for loc in soup.select('sitemap > loc:-soup-contains("/volume_")'):
            page = session.get(loc.text)
            for url in BeautifulSoup(page.content, 'lxml-xml').select('urlset > url'):
                try:
                    link = url.loc.text
                    lastmod = datetime.datetime.fromisoformat(url.lastmod.text).date()
                    uid = get_id(link)
                    k = Key(uid, lastmod)
                    if uid in new:
                        pages.discard(k)
                        pages.add(k)
                        continue

                    if ((inf := uids.get(uid))
                        and keys.get(uid, today) < lastmod
                            and (res := parse(get_soup(session, link), link))):
                        series.add(res[0])
                        res[1].index = inf.index
                        uids[uid] = res[1]
                        pages.discard(k)
                        pages.add(k)
                except Exception as e:
                    warnings.warn(f'({link}): {e}', RuntimeWarning)

    pages.save()
    return series, set(uids.values())


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info)
