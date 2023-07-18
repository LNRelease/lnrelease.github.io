import datetime
import re
import warnings
from collections import Counter, defaultdict
from difflib import get_close_matches
from operator import attrgetter

from utils import Book, Info, Series

NAME = 'misc'

PARSE = re.compile(r'(?P<name>.+?)(?:,|:| -)? +(?:Vol\.|\(?Volume|\(Light Novel) *(?P<volume>\d+\.?\d?)\)?(?::.+)?')
OMNIBUS = re.compile(r'.+(?:Vol\.|\(?Volume) *(?P<volume>\d+-\d+)\)?')
PART = re.compile(r'(?P<name>.+?):? Volume (?P<volume>\d+\.?5?) (?P<part>.+)')
NUMBER = re.compile(r'\b(?P<volume>\d+\.?\d?)\b(?:: .+)?')
SHORT = re.compile(r'\s*#?(?P<volume>\w{1,2})')
SOURCE = re.compile(r'(?P<volume>\d+\.?\d?[^\s:\)]*):? ?.*')
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


def copy(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # apply volume in longest format to others
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    main_diff = diff_list([i.title for i in main_info])
    poss = {main_diff[i]: b for i, b in enumerate(main_books) if b}
    titles = {inf.title: main_books[i] for i, inf in enumerate(main_info)}

    for key, lst in books.items():
        if len(lst) == 1 and not lst[0]:
            inf = info[key][0]
            lst[0] = Book(series.key, inf.link, inf.publisher, inf.title, '1', inf.format, inf.isbn, inf.date)
            continue

        diff = diff_list([i.title for i in info[key]])
        for i, book in enumerate(lst):
            if book:
                continue

            inf = info[key][i]
            if inf.title in titles:
                book = titles[inf.title]
            elif match := get_close_matches(diff[i], poss, n=1, cutoff=0.95):
                book = poss[match[0]]
            else:
                continue
            books[key][i] = Book(series.key, inf.link, inf.publisher, book.name, book.volume, inf.format, inf.isbn, inf.date)
            changed = True
    return changed


def standard(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # simple parsing
    changed = False
    for key, lst in info.items():
        for i, inf in enumerate(lst):
            if match := PARSE.fullmatch(inf.title):
                name = match.group('name')
                vol = match.group('volume')
            elif i == 0 and series.title == inf.title:
                name = inf.title
                vol = '1'
            else:
                continue
            books[key][i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    return changed


def omnibus(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # omnibus voluems
    changed = False
    for key, lst in info.items():
        for i, inf in enumerate(lst):
            if match := OMNIBUS.fullmatch(inf.title):
                name = series.title
                vol = match.group('volume')
                books[key][i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
                changed = True
    return changed


def one(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # assume remaining volumes are individual
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)

    for i, book in enumerate(main_books):
        if book:
            continue

        inf = main_info[i]
        name = inf.title
        vol = '1'
        main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def _guess(series: Series, info: list[Info], books: list[Book]) -> bool:
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


def guess(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # guess volume by looking at previous
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    return _guess(series, main_info, main_books)


def short(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # finds short string that looks right
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    diff = diff_list([sub_nums(i.title) for i in main_info])

    for i, book in enumerate(main_books):
        if book:
            continue

        inf = main_info[i]
        match = NUMBER.fullmatch(diff[i]) or SHORT.fullmatch(diff[i])
        if not match:
            continue
        name = series.title
        vol = match.group('volume')
        main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def part(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # multipart volumes
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)

    for i, book in enumerate(main_books):
        if book:
            continue

        inf = main_info[i]
        if match := PART.fullmatch(inf.title):
            name = match.group('name')
            vol = match.group('volume')
            part = sub_nums(match.group('part'))
            vol += f'.{NUMBER.search(part).group("volume")}'
        else:
            name = inf.title
            vol = '1'
            warnings.warn(f'Part volume parsing error: {inf.title}', RuntimeWarning)
        main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def url(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # searches url for volume
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)

    for i, book in enumerate(main_books):
        if book:
            continue

        inf = main_info[i]
        if match := URL.search(inf.link):
            name = inf.title
            vol = match.group('volume')
            main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    return changed


def secondary(series: Series, info: dict[str, list[Info]], alts: list[Info], books: dict[str, list[Book]]) -> bool:
    # check secondary sources
    changed = False
    sources: defaultdict[str, list[Info]] = defaultdict(list)
    for x in alts:
        if x.serieskey == series.key:
            sources[x.source].append(x)
    if not sources:
        return False

    poss: dict[str, dict[str, Info]] = {}
    for source, lst in sources.items():
        diff = diff_list([i.title for i in lst])
        poss[source] = {x: lst[i] for i, x in enumerate(diff)}
    today = datetime.date.today()
    cutoff = today.replace(year=today.year-5)

    # replace index if unset
    for value in info.values():
        diff = diff_list([i.title for i in value])
        for i, inf in enumerate(value):
            if inf.index == 0:
                indicies: Counter[int] = Counter()
                for source, pos in poss.items():
                    if ((close := get_close_matches(diff[i], pos, n=1, cutoff=0.01))
                            and (index := pos[close[0]].index) != 0):
                        indicies[index] += 1
                if index := indicies.most_common(1):
                    inf.index = index[0][0]

        # trust index if old series and multiple with same date
        if (len({inf.date for inf in value}) != len(value)
                and all(inf.date < cutoff for inf in value)):
            value.sort(key=attrgetter('publisher', 'source', 'index'))
        else:  # index unreliable for current series
            value.sort()

    # find volume in sources
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    diff = diff_list([i.title for i in main_info])

    for i, inf in enumerate(main_info):
        volumes: Counter[str] = Counter()
        for source, pos in poss.items():
            if ((close := get_close_matches(diff[i], pos, n=1, cutoff=0.01))
                    and (match := SOURCE.fullmatch(close[0]))):
                volumes[match.group('volume')] += 1
        if volume := volumes.most_common(1):
            name = series.title
            vol = volume[0][0]
            main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    dupes(main_books)

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


def check(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> list[Book]:
    # check for errors
    for key, lst in books.items():
        if _guess(series, lst, books[key]):
            warnings.warn(f'None volume found: {series.title}', RuntimeWarning)
        if len(set(lst)) != len(lst):
            dupes(lst)
            warnings.warn(f'Duplicate volume found: {series.title}', RuntimeWarning)
    return books


def parse(series: Series, info: dict[str, list[Info]], alts: set[Info]) -> dict[str, list[Book]]:
    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)

    standard(series, info, books)
    guess(series, info, books)
    copy(series, info, books)
    check(series, info, books)
    return books
