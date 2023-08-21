import datetime
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable
from operator import attrgetter
from pathlib import Path

from parse import BOOKS
from utils import FORMATS, Book, Format, Release, Table

OUT = Path('README.md')
DIGITAL = Path('digital.md')
PHYSICAL = Path('physical.md')
YEAR = Path('year')


def write_page(releases: Iterable[Release], output: Path) -> None:
    with open(output, 'w', encoding='utf-8') as file:
        month = 0
        year = 0
        file.write('# Licensed Light Novel Releases\n\n')
        file.write('- Table of contents, visible at https://lnrelease.github.io\n{:toc}')
        for release in releases:
            if year != release.date.year:
                year = release.date.year
                month = 0
                file.write(f'\n\n## {year}\n')
            if month != release.date.month:
                month = release.date.month
                file.write(f'\n### {release.date.strftime("%B")}\n\n')
                file.write('Date|Series|Volume|Publisher|Type|\n')
                file.write(':---:|:---|:---:|:---|:---:|\n')

            name = f'[{release.name}]({release.link})' if release.link else release.name
            file.write(f'{release.date.strftime("%b %d")}|{name}|{release.volume}|{release.publisher}|{release.format}|\n')


def main() -> None:
    releases: defaultdict[Release, list[Book]] = defaultdict(list)
    for book in sorted(Table(BOOKS, Book)):
        releases[Release(*book)].append(book)
    for release, books in releases.items():
        books.sort(key=lambda x: FORMATS.get(x.format, 0))
        formats = {Format.from_str(x.format) for x in books}
        release.format = formats.pop() if len(formats) == 1 else Format.PHYSICAL_DIGITAL
        book = books[0]
        release.link = book.link
        release.isbn = book.isbn
    releases = sorted(releases.keys())

    today = datetime.datetime.today()
    start_date = today - datetime.timedelta(days=7)
    start_date = start_date.replace(day=1).date()
    end_date = today.replace(year=today.year+1, month=12, day=31).date()
    start = bisect_left(releases, start_date, key=attrgetter('date'))
    end = bisect_right(releases, end_date, key=attrgetter('date'), lo=start)
    cur_releases = releases[start:end]

    write_page(cur_releases, OUT)
    write_page((b for b in cur_releases if b.format != Format.PHYSICAL), DIGITAL)
    write_page((b for b in cur_releases if b.format != Format.DIGITAL), PHYSICAL)

    YEAR.mkdir(exist_ok=True)
    start = 0
    while start < len(releases):
        year = releases[start].date.year
        end_date = datetime.datetime(year, 12, 31).date()
        end = bisect_right(releases, end_date, key=attrgetter('date'), lo=start)
        write_page(releases[start:end], YEAR/f'{year}.md')
        start = end


if __name__ == '__main__':
    main()
