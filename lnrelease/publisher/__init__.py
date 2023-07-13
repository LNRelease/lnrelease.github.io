import re
import warnings
from difflib import get_close_matches

from utils import Book, Info, Series

NAME = 'misc'

PARSE = re.compile(r'(?P<name>.+?)(?:,|:| -)? +(?:Vol\.|\(?Volume|\(Light Novel) *(?P<volume>\d+\.?\d?)\)?(?::.+)?')
OMNIBUS = re.compile(r'.+(?:Vol\.|\(?Volume) *(?P<volume>\d+-\d+)\)?')
PART = re.compile(r'(?P<name>.+?):? Volume (?P<volume>\d+\.?5?) (?P<part>.+)')
NUMBER = re.compile(r'\b(?P<volume>\d+\.?\d?)\b(?:: .+)?')
SHORT = re.compile(r'\s*#?(?P<volume>\w{1,2})')
BOOKWALKER = re.compile(r'(?P<volume>\d+\.?\d?[^\s:\)]*):? ?.*')
URL = re.compile(r'-volume-(?P<volume>\d+)')

# number converter for volume parsing
NUM_DICT = {
    re.compile(r'\bzero\b', flags=re.IGNORECASE): '0',
    re.compile(r'\b(first|one|i)\b', flags=re.IGNORECASE): '1',
    re.compile(r'\b(second|two|ii)\b', flags=re.IGNORECASE): '2',
    re.compile(r'\b(third|three|iii)\b', flags=re.IGNORECASE): '3',
    re.compile(r'\b(fourth|four|iv)\b', flags=re.IGNORECASE): '4',
    re.compile(r'\b(fifth|five|v)\b', flags=re.IGNORECASE): '5',
}


def sub_nums(s: str) -> str:
    for pat, repl in NUM_DICT.items():
        s = pat.sub(repl, s)
    return s


def diff_list(titles: list[str]) -> list[str]:
    # returns list from when strings start to differ
    s1 = min(titles)
    s2 = max(titles)
    for i, c in enumerate(s1):
        if c != s2[i]:
            break
    else:
        i = len(s1)
    return [t[i:] for t in titles]


def standard(series: Series, info: list[Info], books: list[Book]) -> bool:
    # simple parsing
    changed = False
    for i, inf in enumerate(info):
        if match := PARSE.fullmatch(inf.title):
            name = match.group('name')
            vol = match.group('volume')
        elif i == 0 and series.title == inf.title:
            name = inf.title
            vol = '1'
        else:
            continue
        books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def omnibus(series: Series, info: list[Info], books: list[Book]) -> bool:
    # omnibus voluems
    changed = False
    for i, inf in enumerate(info):
        if match := OMNIBUS.fullmatch(inf.title):
            name = series.title
            vol = match.group('volume')
            books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    return changed


def guess(series: Series, info: list[Info], books: list[Book]) -> bool:
    # guess volume by looking at previous
    changed = False
    for i, book in enumerate(books):
        if book:
            continue

        inf = info[i]
        if i == 0:
            vol = '1'
        else:
            vol = str(int(float(books[i-1].volume)) + 1)
            if i+1 < len(books) and (b := books[i+1]) and float(vol) >= float(b.volume):
                warnings.warn(f'Volume parsing error: {inf.title}', RuntimeWarning)
        books[i] = Book(series.key, inf.link, inf.publisher, inf.title, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def short(series: Series, info: list[Info], books: list[Book]) -> bool:
    # finds short string that looks right
    changed = False
    diff = diff_list([sub_nums(i.title) for i in info])
    for i, book in enumerate(books):
        if book:
            continue

        inf = info[i]
        match = NUMBER.fullmatch(diff[i]) or SHORT.fullmatch(diff[i])
        if not match:
            continue
        name = series.title
        vol = match.group('volume')
        books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def one(series: Series, info: list[Info], books: list[Book]) -> bool:
    # assume remaining volumes are individual
    changed = False
    for i, book in enumerate(books):
        if book:
            continue

        inf = info[i]
        name = inf.title
        vol = '1'
        books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def part(series: Series, info: list[Info], books: list[Book]) -> bool:
    # multipart volumes
    changed = False
    for i, book in enumerate(books):
        if book:
            continue

        inf = info[i]
        if match := PART.fullmatch(inf.title):
            name = match.group('name')
            vol = match.group('volume')
            part = sub_nums(match.group('part'))
            vol += f'.{NUMBER.search(part).group("volume")}'
        else:
            name = inf.title
            vol = '1'
            warnings.warn(f'Part volume parsing error: {inf.title}', RuntimeWarning)
        books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def bookwalker(series: Series, info: list[Info], alts: list[Info], books: list[Book]) -> bool:
    # checks bookwalker for numbers
    changed = False
    alts = [x for x in alts if x.serieskey == series.key]
    if not alts:
        return False

    diff = diff_list([i.title for i in info])
    poss = diff_list([i.title for i in alts])
    for i, inf in enumerate(info):
        if ((close := get_close_matches(diff[i], poss, n=1, cutoff=0.01))
                and (match := BOOKWALKER.fullmatch(close[0]))):
            name = series.title
            vol = match.group('volume')
            books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    dupes(books)

    # replace index if unset
    for i, inf in enumerate(info):
        if inf.index == 0 and (close := get_close_matches(diff[i], poss, n=1, cutoff=0.01)):
            inf.index = alts[poss.index(close[0])].index
    info.sort()

    return changed


def url(series: Series, info: list[Info], books: list[Book]) -> bool:
    # searches url for number
    changed = False
    for i, book in enumerate(books):
        if book:
            continue

        inf = info[i]
        if match := URL.search(inf.link):
            name = inf.title
            vol = match.group('volume')
            books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    return changed


def dupes(books: list[Book]) -> bool:
    # assume consecutive dupes are multipart
    changed = False
    start = 0
    end = 1
    while end < len(books):
        end += 1
        dupe = False
        while end < len(books) and books[start] == books[end]:
            end += 1
            if books[start] is not None:
                dupe = True
                changed = True
        if dupe:
            part = 0
            for i in range(start, end):
                part += 1
                books[i].volume += f'.{part}'
        start = end
    return changed


def check(series: Series, info: list[Info], books: list[Book]) -> list[Book]:
    # check for errors
    if guess(series, info, books):
        warnings.warn(f'None volume found: {series.title}', RuntimeWarning)
    if len(set(books)) != len(books):
        dupes(books)
        warnings.warn(f'Duplicate volume found: {series.title}', RuntimeWarning)
    return books


def parse(series: Series, info: list[Info], alts: set[Info]) -> list[Book]:
    size = len(info)
    books: list[Book] = [None] * size

    standard(series, info, books)
    guess(series, info, books)
    check(series, info, books)
    return books
