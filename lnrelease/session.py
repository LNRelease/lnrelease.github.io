import os
import random
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import perf_counter_ns, sleep, time
from typing import Self
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {'User-Agent': 'lnrelease.github.io/2.0'}
CHROME = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.3'}
CF_ACCOUNT = os.getenv('CF_ACCOUNT')
CF_KEY = os.getenv('CF_KEY')
CF_HEADERS = {'Content-Type': 'application/json', 'Authorization': f'Bearer {CF_KEY}'}
CF_API = f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/urlscanner/v2'

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
    'global.bookwalker.jp': (1, 3),
    'api.cloudflare.com': (0.1, 0.2),
    'crossinfworld.com': (10, 30),
    'play.google.com': (10, 30),
    'hanashi.media': (30, 600),
    'labs.j-novel.club': (10, 30),
    'api.kodansha.us': (30, 60),
    'www.penguinrandomhouse.ca': (30, 600),
    'legacy.rightstufanime.com': (30, 300),
    'sevenseasentertainment.com': (10, 30),
    'v3-static.supadu.io': (30, 300),
    'tokyopop.com': (30, 300),
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


def limiter(netloc: str) -> Limiter:
    with RATE_LIMITER:
        if netloc not in LIMITERS:
            LIMITERS[netloc] = Limiter(netloc)
        return LIMITERS[netloc]


class Session(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.headers.update(HEADERS)
        self.set_retry()

    def set_retry(self, total: int = 5, backoff_factor: float = 2,
                  status_forcelist: set[int] = {429, 500, 502, 503, 504}) -> None:
        retry = Retry(
            total=total,
            backoff_factor=backoff_factor,
            respect_retry_after_header=True,
            status_forcelist=status_forcelist,
            raise_on_status=False,
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
            warnings.warn(f'Error resolving ({link}): {e}', RuntimeWarning)
        finally:
            self.set_retry()
        return link

    def cf_result(self, url: str, uuid: str, **kwargs) -> requests.Response | None:
        try:
            for _ in range(10):
                page = self.try_get(f'{CF_API}/result/{uuid}', retries=2, **kwargs)
                if (page is None
                    or page.status_code == 400
                    or page.status_code == 404
                        and not page.json().get('task')):
                    return None
                elif page.status_code == 200:
                    jsn = page.json()
                    if not jsn['task']['success']:
                        return None
                    delta = datetime.fromisoformat(jsn['task']['timeEnd']) - datetime.now(timezone.utc)
                    sleep(max(0, delta.total_seconds()))
                    response = jsn['lists']['hashes'][0]
                    return self.try_get(f'{CF_API}/responses/{response}', retries=2, **kwargs)
                sleep(10)
        except Exception as e:
            warnings.warn(f'Error reading scan ({url}|{uuid}): {e}', RuntimeWarning)
        return None

    def cf_search(self, url: str, refresh: int = -1, **kwargs) -> requests.Response | None:
        if not CF_ACCOUNT:
            return None

        kwargs.setdefault('headers', {}).update(CF_HEADERS)
        delta = 365 if refresh == -1 else refresh + random.randrange(refresh * 2)
        cutoff = datetime.now(timezone.utc) - timedelta(days=delta)
        query = f'page.url:"{url}" AND date:>{cutoff.strftime("%Y-%m-%d")}'
        if page := self.try_get(f'{CF_API}/search', retries=2, params={'q': query}, **kwargs):
            results: list[dict] = page.json()['results']
            results.sort(key=lambda x: x['task']['time'], reverse=True)
            for result in results:
                if page := self.cf_result(url, result['task']['uuid'], **kwargs):
                    return page
        return None

    def cf_create(self, url: str, **kwargs) -> requests.Response | None:
        if not CF_ACCOUNT:
            return None

        kwargs.setdefault('headers', {}).update(CF_HEADERS)
        try:
            REQUEST_STATS['api.cloudflare.com'].cache += 1
            with limiter(urlparse(url).netloc).lock:
                for _ in range(5):
                    page = self.post(f'{CF_API}/scan', json={'url': url}, **kwargs)
                    match page.status_code:
                        case 200:
                            sleep(20)
                            return self.cf_result(url, page.json()['uuid'], **kwargs)
                        case 409 | 429:
                            sleep(60)
                            continue
                    raise requests.exceptions.RequestException(page.json()['errors'])
        except requests.exceptions.RequestException as e:
            warnings.warn(f'Error scanning ({url}): {e}', RuntimeWarning)
        return None

    def cf_scan(self, url: str, refresh: int = -1, **kwargs) -> requests.Response | None:
        return self.cf_search(url, refresh, **kwargs) or self.cf_create(url, **kwargs)

    def ia_cache(self, url: str, refresh: int = -1, **kwargs) -> requests.Response | None:
        now = datetime.now(timezone.utc)
        link = f'https://web.archive.org/web/{now.strftime("%Y%m%d%H%M%S")}/{url}'
        page = self.try_get(link, retries=2, **kwargs)
        if refresh == -1:
            return page
        elif page and page.status_code != 404:
            match = IA.fullmatch(page.url)
            time = datetime.strptime(match.group('time') + 'Z', '%Y%m%d%H%M%S%z')
        else:
            time = datetime(1, 1, 1, tzinfo=timezone.utc)
        cutoff = now - timedelta(days=refresh + random.randrange(refresh * 4))
        if time < cutoff:
            link = f'http://web.archive.org/save/{url}'
            REQUEST_STATS['web.archive.org'].cache += 1
            save = self.try_get(link, retries=2, **kwargs)
            if save and save.status_code == 200:
                return save
        return page

    def try_get(self, url: str, retries: int, **kwargs) -> requests.Response | None:
        netloc = urlparse(url).netloc
        for _ in range(retries):
            with limiter(netloc):
                return super().get(url, **kwargs)
        return None

    def get(self, url: str, direct: bool = True, cf: bool = False, ia: bool = False,
            refresh: int = -1, **kwargs) -> requests.Response | None:
        kwargs.setdefault('timeout', 100)
        if match := IA.fullmatch(url):
            url = match.group('url')

        page = self.try_get(url, retries=5, **kwargs) if direct else None
        if page is None or page.status_code == 403:
            self.set_retry(total=2, status_forcelist={500, 502, 503, 504})
            if cf:
                REQUEST_STATS[urlparse(url).netloc].cache += 1
                page = self.cf_scan(url, refresh=refresh, **kwargs)
            if ia and page is None:
                REQUEST_STATS[urlparse(url).netloc].cache += 1
                page = self.ia_cache(url, refresh=refresh, **kwargs)
            self.set_retry()

        if page and page.status_code not in (200, 404):
            warnings.warn(f'Status code {page.status_code}: {url}', RuntimeWarning)

        return page
