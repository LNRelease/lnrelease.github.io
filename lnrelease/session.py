import random
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter_ns, sleep, time
from typing import Self
from urllib.parse import quote, urljoin, urlparse

import requests
import store
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {'User-Agent': 'lnrelease.github.io/1.9'}
CHROME = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.3'}

SHORTENERS = {
    'a.co',
    'amzn.to',
    'apple.co',
    'bit.ly',
}
IA = re.compile(r'https?://web\.archive\.org/web/(?P<time>\d{14})/(?P<url>.+)')


@dataclass
class Stats:
    start: int = 0
    count: int = 0
    cache: int = 0
    wait: int = 0
    total: int = 0

    def begin(self) -> None:
        self.start = perf_counter_ns()
        self.count += 1

    def mid(self) -> None:
        self.wait += perf_counter_ns() - self.start

    def end(self) -> None:
        self.total += perf_counter_ns() - self.start
        self.start = 0

    def __str__(self) -> str:
        return f'{self.count:4d} ({self.cache:4d}); {self.wait/1e9:7.2f} ({self.total/1e9:7.2f})'


RATE_LIMITER = Lock()
DELAYS = {
    'www.amazon.com': (10, 30),
    'books.apple.com': (10, 30),
    'web.archive.org': (10, 30),
    'www.audible.com': (10, 30),
    'www.audible.de': (10, 30),
    'www.audible.co.jp': (10, 30),
    'www.audible.co.uk': (10, 30),
    'www.barnesandnoble.com': (10, 30),
    'www.bing.com': (10, 30),
    'cc.bingj.com': (10, 30),
    'global.bookwalker.jp': (1, 5),
    'crossinfworld.com': (10, 30),
    'play.google.com': (10, 30),
    'webcache.googleusercontent.com': (30, 40),
    'hanashi.media': (30, 600),
    'labs.j-novel.club': (10, 30),
    'api.kodansha.us': (30, 60),
    'www.penguinrandomhouse.ca': (30, 600),
    'legacy.rightstufanime.com': (30, 300),
    'sevenseasentertainment.com': (10, 30),
    'www.viz.com': (30, 60),
    'yenpress.com': (1, 3),
}
LAST_REQUEST: dict[str, float] = {}
REQUEST_STATS: dict[str, Stats] = {netloc: Stats() for netloc in DELAYS}


class Limiter:
    def __init__(self, netloc: str) -> None:
        self.netloc = netloc
        self.lock = Lock()

    def __enter__(self) -> Self:
        self.lock.acquire()
        delay = random.uniform(*DELAYS.get(self.netloc, (0, 0)))
        if not delay:
            warnings.warn(f'No delay for {self.netloc}', RuntimeWarning)
            return
        stats = REQUEST_STATS.get(self.netloc, Stats())
        stats.begin()
        sleep(max(0, delay - time() + LAST_REQUEST.get(self.netloc, 0)))
        stats.mid()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> bool:
        LAST_REQUEST[self.netloc] = time()
        REQUEST_STATS[self.netloc].end()
        self.lock.release()
        return isinstance(exc_value, requests.exceptions.RequestException)


LIMITERS: dict[str, Limiter] = {}


def limiter(netloc: str) -> Lock:
    with RATE_LIMITER:
        if netloc not in LIMITERS:
            LIMITERS[netloc] = Limiter(netloc)
        return LIMITERS[netloc]


class Session(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.headers.update(HEADERS)
        self.set_retry()
        self.skip_google = -2

    def set_retry(self, total: int = 5, backoff_factor: float = 2,
                  status_forcelist: set[int] = {429, 500, 502, 503, 504}) -> None:
        retry = Retry(
            total=total,
            backoff_factor=backoff_factor,
            respect_retry_after_header=True,
            status_forcelist=status_forcelist
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.mount('http://', adapter)
        self.mount('https://', adapter)

    def resolve(self, link: str, force: bool = False, **kwargs) -> str:
        netloc = urlparse(link).netloc
        if not force and netloc not in SHORTENERS:
            return link

        try:
            self.set_retry(status_forcelist={})
            kwargs.setdefault('timeout', 10)
            kwargs.setdefault('allow_redirects', False)
            if kwargs.get('headers', {}).get('User-Agent'):
                page = super().get(link, **kwargs)
            else:
                page = self.head(link, **kwargs)
                if page.status_code not in (200, 301):
                    page = super().get(link, **kwargs)
            if page.status_code == 301:
                link = urljoin(page.url, page.headers.get('Location'))
        except requests.exceptions.RequestException as e:
            warnings.warn(f'Error resolving {link}: {e}', RuntimeWarning)
        finally:
            self.set_retry()
        return link

    def google_cache(self, url: str, **kwargs) -> requests.Response | None:
        if self.skip_google > 0:
            return None

        url = f'https://webcache.googleusercontent.com/search?q=cache:{quote(url)}'
        page = self.try_get(url, retries=5, **kwargs)

        if page and page.status_code == 429:
            warnings.warn(f'Google code 429: {url}', RuntimeWarning)
            self.skip_google = 1
            return None
        if page and b' - Google Search</title>' in page.content:
            self.skip_google += 1
            return None
        return page

    def _bing_cache(self, query: str, url: str, **kwargs) -> requests.Response | None:
        link = f'https://www.bing.com/search?q={quote(query)}&go=Search&qs=bs&form=QBRE'
        page = self.try_get(link, retries=5, **kwargs)
        if not page:
            return None

        soup = BeautifulSoup(page.content, 'lxml')
        norm = urlparse(store.normalise(self, url))
        module = store.get_store(norm.netloc)
        link = 'https://cc.bingj.com/cache.aspx'

        page = None
        for li in soup.select('ol#b_results > li.b_algo'):
            attr = li.find('div', {'u': True})
            u = urlparse(store.normalise(self, li.a.get('href')))
            if not (attr and norm.path == u.path
                    and module is store.get_store(u.netloc)):
                continue

            lst = attr['u'].split('|')
            params = {'d': lst[2], 'w': lst[3]}

            page = self.try_get(link, retries=5, params=params, **kwargs)
            if (page and page.status_code == 200
                    and not page.content.endswith(b'<!-- Apologies:End -->')):
                break

        return page

    def bing_cache(self, url: str, **kwargs) -> requests.Response | None:
        netloc = urlparse(url).netloc
        end = url.split(netloc)[-1]
        return (self._bing_cache(end, url, **kwargs)
                or self._bing_cache(netloc + end, url, **kwargs))

    def ia_cache(self, url: str, ia_save: int = -1, **kwargs) -> requests.Response | None:
        now = datetime.now(timezone.utc)
        link = f'https://web.archive.org/web/{now.strftime("%Y%m%d%H%M%S")}/{url}'
        page = self.try_get(link, retries=2, **kwargs)
        if ia_save == -1:
            return page
        elif page.status_code != 404:
            match = IA.fullmatch(page.url)
            time = datetime.strptime(match.group('time') + 'Z', '%Y%m%d%H%M%S%z')
            days = (now - time).days - ia_save
        else:
            days = 0xFFFF
        if days <= 0:
            return page
        elif random.randrange(ia_save * 4) < days:
            link = f'http://web.archive.org/save/{url}'
            return self.try_get(link, retries=2, **kwargs)
        return page

    def get_cache(self, url: str, ia_save: int, **kwargs) -> requests.Response | None:
        google = self.google_cache(url, headers=CHROME, **kwargs)
        if google and google.status_code == 200:
            return google

        bing = self.bing_cache(url, headers=CHROME, **kwargs)
        if bing:
            return bing

        return self.ia_cache(url, ia_save=ia_save, **kwargs)

    def try_get(self, url: str, retries: int, **kwargs) -> requests.Response | None:
        netloc = urlparse(url).netloc
        for _ in range(retries):
            with limiter(netloc):
                page = super().get(url, **kwargs)
                return page
        return None

    def get(self, url: str, direct: bool = True, web_cache: bool = False,
            ia_save: int = -1, **kwargs) -> requests.Response | None:
        kwargs.setdefault('timeout', 100)
        if match := IA.fullmatch(url):
            url = match.group('url')

        page = self.try_get(url, retries=5, **kwargs) if direct else None
        if web_cache and (not page or page.status_code == 403):
            REQUEST_STATS[urlparse(url).netloc].cache += 1
            self.set_retry(total=2, status_forcelist={500, 502, 503, 504})
            page = self.get_cache(url, ia_save=ia_save, **kwargs)
            self.set_retry()

        if page and page.status_code not in (200, 404):
            warnings.warn(f'Status code {page.status_code}: {url}', RuntimeWarning)

        return page
