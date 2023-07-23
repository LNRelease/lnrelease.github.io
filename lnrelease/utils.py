import csv
import datetime
import re
import unicodedata
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {'User-Agent': 'lnrelease.github.io/1.1'}

TITLE = re.compile(r' \((?:light )?novels?\)', flags=re.IGNORECASE)
NONWORD = re.compile(r'\W')


PHYSICAL = ['Physical', 'Hardcover', 'Hardback', 'Paperback']
DIGITAL = ['Digital']
FORMATS = {x: i for i, x in enumerate(PHYSICAL + DIGITAL)}


def clean_str(s: str) -> str:
    return NONWORD.sub('', unicodedata.normalize('NFKD', s)).lower()


class Format(StrEnum):
    # spacer to align text, github yeets input tag
    NONE = ''
    PHYSICAL = '<input class="spacer" alt="🖥️" type="image" disabled>📖'
    DIGITAL = '🖥️<input class="spacer" alt="📖" type="image" disabled>'
    PHYSICAL_DIGITAL = '🖥️📖'

    @staticmethod
    def from_str(s: str) -> Self:
        if s in PHYSICAL:
            return Format.PHYSICAL
        elif s in DIGITAL:
            return Format.DIGITAL
        warnings.warn(f'Unknown format: {s}', RuntimeWarning)
        return Format.NONE


@dataclass
class Link:
    link: str
    date: datetime.date

    @classmethod
    def from_db(cls, link: str, date: str) -> None:
        date = datetime.date.fromisoformat(date) if date else None
        return cls(link, date)

    def __eq__(self, other: Self) -> bool:
        return isinstance(other, self.__class__) and self.link == other.link

    def __lt__(self, other: Self) -> bool:
        return self.link < other.link

    def __hash__(self) -> int:
        return hash(self.link)

    def __iter__(self) -> Iterator[Self]:
        yield self.link
        yield self.date


@dataclass
class Series:
    key: str
    title: str

    def __post_init__(self) -> None:
        self.title = TITLE.sub('', self.title).replace('’', "'").strip()
        self.key = self.key or clean_str(self.title)

    @classmethod
    def from_db(cls, key: str, title: str) -> Self:
        return cls(key, title)

    def __eq__(self, other: Self) -> bool:
        return isinstance(other, self.__class__) and self.key == other.key

    def __lt__(self, other: Self) -> bool:
        return self.key < other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def __iter__(self) -> Iterator[Self]:
        yield self.key
        yield self.title


@dataclass
class Info:
    serieskey: str
    link: str
    source: str
    publisher: str
    title: str
    index: int  # unreliable, 0 is unset
    format: str
    isbn: str
    date: datetime.date

    def __post_init__(self) -> None:
        self.title = TITLE.sub('', self.title).replace('’', "'").strip()

    @classmethod
    def from_db(cls, serieskey: str, link: str, source: str, publisher: str,
                title: str, index: str, format: str, isbn: str, date: str) -> Self:
        index = int(index)
        date = datetime.date.fromisoformat(date)
        return cls(serieskey, link, source, publisher, title, index, format, isbn, date)

    def __eq__(self, other: Self) -> bool:
        return (isinstance(other, self.__class__)
                and self.link == other.link
                and self.format == other.format)

    def __lt__(self, other: Self) -> bool:
        if self.serieskey != other.serieskey:
            return self.serieskey < other.serieskey
        elif self.publisher != other.publisher:
            return self.publisher < other.publisher
        elif self.source != other.source:
            return self.source < other.source
        elif self.format != other.format:
            return self.format < other.format
        elif self.date != other.date:
            return self.date < other.date
        elif self.index != other.index:
            return self.index < other.index
        return self.link < other.link

    def __hash__(self) -> int:
        return hash((self.link, self.format))

    def __iter__(self) -> Iterator[Self]:
        yield self.serieskey
        yield self.link
        yield self.source
        yield self.publisher
        yield self.title
        yield self.index
        yield self.format
        yield self.isbn
        yield self.date


@dataclass
class Book:
    serieskey: str
    link: str
    publisher: str
    name: str
    volume: str
    format: str
    isbn: str
    date: datetime.date

    @classmethod
    def from_db(cls, serieskey: str, link: str, publisher: str,
                name: str, volume: str, format: str, isbn: str, date: str) -> Self:
        date = datetime.date.fromisoformat(date)
        return cls(serieskey, link, publisher, name, volume, format, isbn, date)

    def __eq__(self, other: Self) -> bool:
        return (isinstance(other, self.__class__)
                and self.serieskey == other.serieskey
                and self.publisher == other.publisher
                and self.name == other.name
                and self.volume == other.volume
                and self.format == other.format
                and self.date == other.date)

    def __lt__(self, other: Self) -> bool:
        if self.serieskey != other.serieskey:
            return self.serieskey < other.serieskey
        elif self.format != other.format:
            return self.format < other.format
        elif self.publisher != other.publisher:
            return self.publisher < other.publisher
        elif self.date != other.date:
            return self.date < other.date
        elif len(self.volume) != len(other.volume):
            pad = max(len(self.volume), len(other.volume))
            return self.volume.zfill(pad) < other.volume.zfill(pad)
        elif self.volume != other.volume:
            return self.volume < other.volume
        return self.name < other.name

    def __hash__(self) -> int:
        return hash((self.serieskey, self.publisher, self.name, self.volume, self.format, self.date))

    def __iter__(self) -> Iterator[Self]:
        yield self.serieskey
        yield self.link
        yield self.publisher
        yield self.name
        yield self.volume
        yield self.format
        yield self.isbn
        yield self.date


@dataclass
class Release:
    serieskey: str
    link: str
    publisher: str
    name: str
    volume: str
    format: Format
    isbn: str
    date: datetime.date

    def __eq__(self, other: Self) -> bool:
        return (isinstance(other, self.__class__)
                and self.serieskey == other.serieskey
                and self.publisher == other.publisher
                and self.name == other.name
                and self.volume == other.volume
                and self.date == other.date)

    def __lt__(self, other: Self) -> bool:
        if self.date != other.date:
            return self.date < other.date
        elif self.serieskey != other.serieskey:
            return self.serieskey < other.serieskey
        elif self.publisher != other.publisher:
            return self.publisher < other.publisher
        elif self.name != other.name:
            return self.name < other.name
        elif len(self.volume) != len(other.volume):
            pad = max(len(self.volume), len(other.volume))
            return self.volume.zfill(pad) < other.volume.zfill(pad)
        return self.volume < other.volume

    def __hash__(self) -> int:
        return hash((self.serieskey, self.publisher, self.name, self.volume, self.date))


class Table(set[Link | Info | Book | Series]):
    def __init__(self, file: Path, cls: type[Link | Info | Book | Series]) -> None:
        super().__init__()
        self.file = file
        self.cls = cls
        if file.is_file():
            with open(self.file, 'r', encoding='utf-8', newline='') as f:
                for line in csv.reader(f):
                    self.add(self.cls.from_db(*line))

    def save(self) -> None:
        with open(self.file, 'w', encoding='utf-8', newline='') as f:
            csv.writer(f).writerows(sorted(self))

    def replace(self, elem: Link | Info | Book | Series) -> None:
        self.discard(elem)
        self.add(elem)


class Session(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.headers.update(HEADERS)
        retry = Retry(
            total=10,
            backoff_factor=1,
            respect_retry_after_header=True,
            status_forcelist={429, 500, 502, 503, 504}
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.mount('http://', adapter)
        self.mount('https://', adapter)

    def get(self, url, timeout=1000, **kwargs) -> requests.Response:
        kwargs['timeout'] = timeout
        return super().get(url, **kwargs)
