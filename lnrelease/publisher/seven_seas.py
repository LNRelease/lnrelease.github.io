from utils import Book, Info, Series

from . import check, copy, guess, omnibus, one, secondary, short, standard

NAME = 'Seven Seas Entertainment'


def parse(series: Series, info: dict[str, list[Info]], alts: set[Info]) -> dict[str, list[Book]]:
    if 'Digital' not in info and any(alt.serieskey == series.key
                                     and alt.publisher == NAME
                                     and alt.format == 'Digital' for alt in alts):
        # copy physical dates if digital releases found elsewhere
        info['Digital'] = []
        for inf in info['Physical']:
            i = Info(series.key, inf.link, inf.source, NAME, inf.title, inf.index, 'Digital', '', inf.date)
            info['Digital'].append(i)

    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    size = len(main_info)

    standard(series, info, books)
    omnibus(series, info, books)
    short(series, info, books)
    if main_books.count(None) < size - 1:
        one(series, info, books)
    else:
        secondary(series, info, alts, books)
        guess(series, info, books)
    copy(series, info, books)
    check(series, info, books)
    return books
