import csv
import datetime
import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {'User-Agent': 'lnrelease.github.io/1.0'}

TITLE = re.compile(r' \((light )?novels?\)', flags=re.IGNORECASE)


class Format(StrEnum):
    NONE = ''
    PHYSICAL = 'Physical'
    DIGITAL = 'Digital'
    PHYSICAL_DIGITAL = 'Physical & Digital'

    def opposite(self) -> Self:
        match self:
            case Format.PHYSICAL:
                return Format.DIGITAL
            case Format.DIGITAL:
                return Format.PHYSICAL
            case Format.NONE:
                return Format.PHYSICAL_DIGITAL
            case Format.PHYSICAL_DIGITAL:
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
        self.key = self.key or re.sub(r'\W', '', unicodedata.normalize('NFKD', self.title)).lower()

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
    index: int  # 0 is unset, unreliable
    format: Format
    isbn: str
    date: datetime.date

    def __post_init__(self) -> None:
        self.title = TITLE.sub('', self.title).replace('’', "'").strip()

    @classmethod
    def from_db(cls, serieskey: str, link: str, source: str, publisher: str,
                title: str, index: str, format: str, isbn: str, date: str) -> Self:
        index = int(index)
        format = Format(format)
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
    format: Format
    isbn: str
    date: datetime.date

    @classmethod
    def from_db(cls, serieskey: str, link: str, publisher: str,
                name: str, volume: str, format: str, isbn: str, date: str) -> Self:
        format = Format(format)
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


class Table:
    def __init__(self, file: Path, cls: type[Link | Info | Book | Series]) -> None:
        self.file = file
        self.cls = cls
        self.rows: set[self.cls] = set()
        if file.is_file():
            with open(self.file, 'r', encoding='utf-8', newline='') as f:
                for line in csv.reader(f):
                    self.rows.add(self.cls.from_db(*line))

    def save(self) -> None:
        with open(self.file, 'w', encoding='utf-8', newline='') as f:
            csv.writer(f).writerows(sorted(self.rows))

    def add(self, row: Link | Info | Book | Series) -> None:
        self.rows.add(row)

    def update(self, rows: Iterable[Link | Info | Book | Series]) -> None:
        self.rows.update(rows)


class Session(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.headers.update(HEADERS)
        retry = Retry(
            total=10,
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.mount('http://', adapter)
        self.mount('https://', adapter)

    def get(self, url, timeout=1000, **kwargs) -> requests.Response:
        kwargs['timeout'] = timeout
        return super().get(url, **kwargs)
