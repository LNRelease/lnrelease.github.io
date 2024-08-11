from utils import Book, Info, Series

from . import NUMBER, check, copy, guess, omnibus, one, part, secondary, short, standard

NAME = 'Yen Press'


def parse(series: Series, info: dict[str, list[Info]],
          links: set[Info]) -> dict[str, list[Book]]:
    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        # remove duplicates
        seen = set()
        for inf in lst.copy():
            title = inf.title
            if title in seen:
                lst.remove(inf)
            seen.add(title)
        books[format] = [None] * len(lst)

    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    size = len(main_info)

    standard(series, info, books)
    omnibus(series, info, books)
    short(series, info, books)
    todo = [i for i, book in enumerate(main_books) if not book]
    if len(todo) == 0:
        pass
    elif all((' Volume ' in main_info[i].title
              or ' Vol. ' in main_info[i].title)
             and len(NUMBER.findall(main_info[i].title)) > 1
             for i in todo):
        part(series, info, books)
    elif len(todo) < size - 1:
        one(series, info, books)
    else:
        secondary(series, info, links, books)
        short(series, info, books)
        guess(series, info, books)

    copy(series, info, books)
    check(series, info, books)
    return books
