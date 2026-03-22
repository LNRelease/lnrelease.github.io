from dataclasses import replace
from itertools import chain

from utils import Book, Info, Series

from . import check, copy, dates, guess, standard

NAME = 'Hanashi Media'


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    linked = {alt for lst in info.values() for inf in lst for alt in inf.alts}
    fdates = {f: {inf.date for inf in lst} for f, lst in info.items()}
    titles = set()
    for lst in info.values():
        for inf in lst:
            titles.add(inf.title)
            for link in inf.alts:
                for i in info.get(link, ()):
                    titles.add(i.title)
    for inf in chain.from_iterable(links.values()):
        if (inf.serieskey == series.key
            and inf.publisher == NAME
            and inf.link not in linked
            and inf.format in info
                and inf.date not in fdates[inf.format]):
            info[inf.format].append(replace(inf, index=0))
            fdates[inf.format].add(inf.date)
    dates(info, links)

    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)

    standard(series, info, books)
    guess(series, info, books)
    copy(series, info, books)
    check(series, info, books)
    return books
