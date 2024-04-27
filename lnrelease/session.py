import random
import warnings
from threading import Lock
from time import sleep, time
from typing import Self
from urllib.parse import quote, urljoin, urlparse

import requests
import store
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {'User-Agent': 'lnrelease.github.io/1.7'}

SHORTENERS = {
    'a.co',
    'amzn.to',
    'apple.co',
    'bit.ly',
}


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
        sleep(max(0, delay - time() + LAST_REQUEST.get(self.netloc, 0)))
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> bool:
        LAST_REQUEST[self.netloc] = time()
        self.lock.release()
        return isinstance(exc_value, requests.exceptions.RequestException)


RATE_LIMITER = Lock()
DELAYS = {
    'www.amazon.ca': (10, 30),
    'www.amazon.co.uk': (10, 30),
    'www.amazon.com': (10, 30),
    'www.amazon.com.au': (10, 30),
    'books.apple.com': (10, 30),
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
    'www.kobo.com': (10, 30),
    'api.kodansha.us': (30, 60),
    'www.penguinrandomhouse.ca': (30, 600),
    'legacy.rightstufanime.com': (30, 300),
    'sevenseasentertainment.com': (10, 30),
    'www.viz.com': (30, 300),
    'yenpress.com': (1, 3),
}
LAST_REQUEST: dict[str, float] = {}
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
        self.skip_google = False

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
        if self.skip_google:
            return None

        url = f'https://webcache.googleusercontent.com/search?q=cache:{quote(url)}'
        page = self.try_get(url, retries=5, **kwargs)

        if page and page.status_code == 429:
            warnings.warn(f'Google code 429: {url}', RuntimeWarning)
            self.skip_google = True
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
        for div in soup.select('ol#b_results > li.b_algo'):
            attr = div.find('div', {'u': True})
            u = urlparse(store.normalise(self, div.a['href']))
            if not (attr and norm.path == u.path
                    and module is store.get_store(u.netloc)):
                continue

            lst = attr['u'].split('|')
            params = {'d': lst[2], 'w': lst[3]}

            page = self.try_get(link, retries=5, params=params, **kwargs)
            if page and page.status_code == 200:
                break

        return page

    def bing_cache(self, url: str, **kwargs) -> requests.Response | None:
        netloc = urlparse(url).netloc
        end = url.split(netloc)[-1]
        return (self._bing_cache(f'url:{url}', url, **kwargs)
                or self._bing_cache(netloc + end, url, **kwargs)
                or self._bing_cache(end, url, **kwargs))

    def get_cache(self, url: str, **kwargs) -> requests.Response | None:
        google = self.google_cache(url, **kwargs)
        if google and google.status_code == 200:
            return google

        bing = self.bing_cache(url, **kwargs)
        return bing or google

    def try_get(self, url: str, retries: int, **kwargs) -> requests.Response | None:
        netloc = urlparse(url).netloc
        for _ in range(retries):
            with limiter(netloc):
                page = super().get(url, **kwargs)
                return page
        return None

    def get(self, url: str, web_cache: bool = False, **kwargs) -> requests.Response:
        kwargs.setdefault('timeout', 100)
        if not web_cache:
            page = self.try_get(url, retries=5, **kwargs)
            if not page or page.status_code == 403:  # cloudflare
                web_cache = True

        if web_cache:
            self.set_retry(total=2, status_forcelist={500, 502, 503, 504})
            page = self.get_cache(url, **kwargs)
            self.set_retry()
        if page.status_code not in (200, 404):
            warnings.warn(f'Status code {page.status_code}: {url}', RuntimeWarning)

        return page
