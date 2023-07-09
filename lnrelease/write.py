import datetime
from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from copy import copy
from operator import attrgetter
from pathlib import Path

from parse import BOOKS
from utils import Book, Format, Table

OUT = Path('README.md')
DIGITAL = Path('digital.md')
PHYSICAL = Path('physical.md')
YEAR = Path('year')


def write_page(books: Iterable[Book], output: Path) -> None:
    with open(output, 'w', encoding='utf-8') as file:
        month = 0
        year = 0
        file.write('# Licensed Light Novel Releases\n\n')
        file.write('- Table of contents, visible at https://lnrelease.github.io\n{:toc}')
        for book in books:
            if year != book.date.year:
                year = book.date.year
                month = 0
                file.write(f'\n\n## {year}\n')
            if month != book.date.month:
                month = book.date.month
                file.write(f'\n### {book.date.strftime("%B")}\n\n')
                file.write('Date|Series|Volume|Publisher|Type|\n')
                file.write(':---|:---|:---:|:---|---|\n')

            name = f'[{book.name}]({book.link})' if book.link else book.name
            match book.format:
                case Format.PHYSICAL:
                    format = '<span style="visibility: hidden">💻</span>📖'
                case Format.DIGITAL:
                    format = '💻<span style="visibility: hidden">📖</span>'
                case Format.PHYSICAL_DIGITAL:
                    format = '💻📖'
            file.write(f'{book.date.strftime("%b %d")}|{name}|{book.volume}|{book.publisher}|{format}|\n')


def main() -> None:
    books: list[Book] = []
    rows = Table(BOOKS, Book).rows
    for book in rows:
        opp = copy(book)
        opp.format = opp.format.opposite()
        if opp in rows:
            if book.format == Format.PHYSICAL:
                opp.format = Format.PHYSICAL_DIGITAL
                books.append(opp)  # add for both
        else:
            books.append(book)
    books.sort(key=attrgetter('date', 'name', 'format', 'publisher', 'volume', 'serieskey'))

    today = datetime.date.today()
    start_date = today.replace(day=1)
    end_date = today.replace(year=today.year+1, month=12, day=31)
    start = bisect_left(books, start_date, key=attrgetter('date'))
    end = bisect_right(books, end_date, key=attrgetter('date'), lo=start)
    cur_books = books[start:end]
    write_page(cur_books, OUT)
    write_page((b for b in cur_books if b.format != Format.PHYSICAL), DIGITAL)
    write_page((b for b in cur_books if b.format != Format.DIGITAL), PHYSICAL)

    YEAR.mkdir(exist_ok=True)
    start = 0
    while start < len(books):
        year = books[start].date.year
        end_date = datetime.datetime(year, 12, 31).date()
        end = bisect_right(books, end_date, key=attrgetter('date'), lo=start)
        write_page(books[start:end], YEAR/f'{year}.md')
        start = end


if __name__ == '__main__':
    main()
