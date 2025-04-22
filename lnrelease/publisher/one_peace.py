import re
from collections import Counter
from itertools import chain

from utils import EPOCH, Book, Format, Info, Series

from . import PARSE, check, copy, guess, standard

NAME = 'One Peace Books'


def norm(title: str) -> str:
    if match := PARSE.fullmatch(title):
        name = match.group('name')
        vol = match.group('volume')
        return f'{name} Volume {vol}'
    return title


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    ftitles: dict[Format, set[str]] = {}
    fdates: dict[Format, dict[str, Counter]] = {}
    for format, lst in info.items():
        fmt = Format.from_str(format)
        titles = ftitles.setdefault(fmt, set())
        dates = fdates.setdefault(fmt, {})
        for inf in lst:
            title = norm(inf.title)
            titles.add(title)
            dates[title] = Counter()

    for inf in chain.from_iterable(links.values()):
        if inf.serieskey != series.key or inf.publisher != NAME:
            continue

        fmt = Format.from_str(inf.format)
        titles = ftitles.get(fmt)
        dates = fdates.get(fmt)
        title = norm(inf.title)
        if titles and title not in titles and Series(None, title) == series:
            i = Info(series.key, inf.link, inf.source, NAME, title, 0, inf.format, inf.isbn, inf.date)
            info[fmt.name.title()].append(i)
            titles.add(title)
            fdates[fmt][title] = Counter((i.date,))
        elif inf.date != EPOCH and (counter := dates.get(norm(inf.title))) is not None:
            counter[inf.date] += 1

    for format, lst in info.items():
        dates = fdates[Format.from_str(format)]
        for inf in lst:
            if inf.date == EPOCH and (counter := dates.get(norm(inf.title))):
                date = sorted(counter.most_common(), key=lambda x: (-x[1], x[0]))
                inf.date = date[0][0]

    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)

    standard(series, info, books)
    guess(series, info, books)
    copy(series, info, books)
    check(series, info, books)
    return books
