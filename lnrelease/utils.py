import csv
import datetime
import re
import unicodedata
import warnings
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Self

import store

TITLE = re.compile(r' [\(\[](?:(?:bl )?(?:light )?novels?|audio(?:book)?|(?:\w+ )?e?book)[\)\]]|spin[- ]?off', flags=re.IGNORECASE)
SERIES = re.compile(r'(?:\b|\s|,|:)+(?:[\(\[](?:(?:bl )?(?:light )?novels?|audio(?:book)?|e?book|spin[- ]?off)[\)\[]|(?:(vol\.|volume|part) \d[\d\-\.]*)|omnibus|(?:special|collector\'s) edition)(?:(?=\W)|$)', flags=re.IGNORECASE)
NONWORD = re.compile(r'\W')
IA = re.compile(r'https?://web\.archive\.org/web/\d{14}/(?P<url>.+)')

PHYSICAL = ('Physical', 'Hardcover', 'Hardback', 'Paperback')
DIGITAL = ('Digital', 'eBook')
AUDIOBOOK = ('Audiobook', 'Audio')
FORMATS = {x: i for i, x in enumerate(PHYSICAL + DIGITAL + AUDIOBOOK)}

PRIMARY = (
    'Cross Infinite World',
    'Hanashi Media',
    'J-Novel Club',
    'Kodansha',
    'Seven Seas Entertainment',
    'TOKYOPOP',
    'VIZ Media',
    'Yen Press',
)
SECONDARY = (
    'BOOK☆WALKER',
    'Penguin Random House',
    'Crunchyroll',
    'Apple',
    'Barnes & Noble',
    'Google',
    'Kobo',
    'Audible',
    'Amazon',
)
SOURCES = {x: i for i, x in enumerate(PRIMARY + SECONDARY)}

# placeholder date
EPOCH = datetime.date(1, 1, 1)


def clean_str(s: str) -> str:
    return NONWORD.sub('', unicodedata.normalize('NFKD', s)).lower()


def volume_lt(a: str, b: str) -> bool:
    try:
        af = float(a.split('-')[0])
        bf = float(b.split('-')[0])
        return af < bf
    except ValueError:
        return a < b


class Format(StrEnum):
    NONE = ''
    PHYSICAL = '📖'
    DIGITAL = '🖥️'
    PHYSICAL_DIGITAL = '🖥️📖'
    AUDIOBOOK = '🔊'

    @staticmethod
    def from_str(s: str) -> Self:
        if s in PHYSICAL:
            return Format.PHYSICAL
        elif s in DIGITAL:
            return Format.DIGITAL
        elif s in AUDIOBOOK:
            return Format.AUDIOBOOK
        warnings.warn(f'Unknown format: {s}', RuntimeWarning)
        return Format.NONE

    def is_digital(self) -> bool:
        return self == Format.DIGITAL or self == Format.PHYSICAL_DIGITAL

    def is_physical(self) -> bool:
        return self == Format.PHYSICAL or self == Format.PHYSICAL_DIGITAL


@dataclass
class Key:
    key: str
    date: datetime.date

    @classmethod
    def from_db(cls, link: str, date: str) -> None:
        date = datetime.date.fromisoformat(date) if date else None
        return cls(link, date)

    def __eq__(self, other: Self) -> bool:
        return isinstance(other, self.__class__) and self.key == other.key

    def __lt__(self, other: Self) -> bool:
        return self.key < other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def __iter__(self) -> Iterator[Self]:
        yield self.key
        yield self.date


@dataclass
class Series:
    key: str
    title: str

    def __post_init__(self) -> None:
        self.title = SERIES.sub('', self.title).replace('’', "'").strip()
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
    alts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if match := IA.fullmatch(self.link):
            self.link = match.group('url')
        self.title = TITLE.sub('', self.title).replace('’', "'").strip()
        self.date = self.date or EPOCH

    @classmethod
    def from_db(cls, serieskey: str, link: str, source: str, publisher: str, title: str,
                index: str, format: str, isbn: str, date: str, *alts: str) -> Self:
        index = int(index)
        date = datetime.date.fromisoformat(date)
        alts = list(alts)
        return cls(serieskey, link, source, publisher, title, index, format, isbn, date, alts)

    def __eq__(self, other: Self) -> bool:
        return (isinstance(other, self.__class__)
                and store.equal(self.link, other.link)
                and self.format == other.format)

    def __lt__(self, other: Self) -> bool:
        if self.serieskey != other.serieskey:
            return self.serieskey < other.serieskey
        elif self.publisher != other.publisher:
            return self.publisher < other.publisher
        elif self.source != other.source:
            return SOURCES[self.source] < SOURCES[other.source]
        elif self.format != other.format:
            return self.format < other.format
        elif self.date != other.date:
            return self.date < other.date
        elif self.index != other.index:
            return self.index < other.index
        return self.link < other.link

    def __hash__(self) -> int:
        return hash((store.hash_link(self.link), self.format))

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
        self.alts.sort()
        for alt in self.alts:
            yield alt


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
    def from_db(cls, serieskey: str, link: str, publisher: str, name: str,
                volume: str, format: str, isbn: str, date: str) -> Self:
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
        elif self.volume != other.volume:
            return volume_lt(self.volume, other.volume)
        return self.name < other.name

    def __hash__(self) -> int:
        return hash((self.serieskey,
                     self.publisher,
                     self.name,
                     self.volume,
                     self.format,
                     self.date))

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
                and self.publisher == other.publisher
                and clean_str(self.name) == clean_str(other.name)
                and self.volume == other.volume
                and (self.format in AUDIOBOOK) == (other.format in AUDIOBOOK)
                and self.date == other.date)

    def __lt__(self, other: Self) -> bool:
        if self.date != other.date:
            return self.date < other.date
        elif self.serieskey != other.serieskey:
            return self.serieskey < other.serieskey
        elif self.publisher != other.publisher:
            return self.publisher < other.publisher
        elif self.volume != other.volume:
            return volume_lt(self.volume, other.volume)
        return self.name < other.name

    def __hash__(self) -> int:
        return hash((self.publisher,
                     clean_str(self.name),
                     self.volume,
                     self.format in AUDIOBOOK,
                     self.date))


class Table(set[Key | Info | Book | Series]):
    def __init__(self, file: Path, cls: type[Key | Info | Book | Series]) -> None:
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


def find_series(title: str, series: set[Series]) -> Series | None:
    s = clean_str(title)
    matches: list[Series] = []
    for serie in series:
        if s.startswith(serie.key):
            matches.append(serie)
    if matches:
        return max(matches, key=lambda x: len(x.title))
    return None
