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
AUDIOBOOK = Path('audiobook.md')
YEAR = Path('year')


def write_page(releases: Iterable[Release], output: Path, title: str) -> None:
    with open(output, 'w', encoding='utf-8') as file:
        month = 0
        year = 0
        file.write(title)
        file.write('\n\n- Table of contents, visible at https://lnrelease.github.io\n{:toc}')
        for release in releases:
            if year != release.date.year:
                year = release.date.year
                month = 0
                file.write(f'\n\n## [{year}](/year/{year}.md)\n')
            if month != release.date.month:
                month = release.date.month
                file.write(f'\n### {release.date.strftime("%B")}\n\n')
                file.write('Date|Series|Volume|Publisher|Type|\n')
                file.write('---|---|---|---|---|\n')

            name = f'[{release.name}]({release.link})' if release.link else release.name
            file.write(f'{release.date.strftime("%b %d")}|{name}|{release.volume}|{release.publisher}|{release.format}|\n')


def main() -> None:
    dic: defaultdict[Release, list[Book]] = defaultdict(list)
    for book in sorted(Table(BOOKS, Book)):
        dic[Release(*book)].append(book)
    for release, books in dic.items():
        books.sort(key=lambda b: FORMATS.get(b.format, 0))
        formats = {Format.from_str(b.format) for b in books}
        release.format = formats.pop() if len(formats) == 1 else Format.PHYSICAL_DIGITAL
        if release.format == Format.AUDIOBOOK:
            release.name += ' (Audiobook)'
        book = books[0]
        release.link = book.link
        release.isbn = book.isbn
    releases: list[Release] = sorted(dic)

    today = datetime.datetime.today()
    start_date = today - datetime.timedelta(days=7)
    start_date = start_date.replace(day=1).date()
    end_date = today.replace(year=today.year+1, month=12, day=31).date()
    start = bisect_left(releases, start_date, key=attrgetter('date'))
    end = bisect_right(releases, end_date, key=attrgetter('date'), lo=start)
    cur_releases = releases[start:end]

    title = 'Light Novel Releases'
    write_page((b for b in cur_releases if b.format != Format.AUDIOBOOK),
                OUT, f'# Licensed {title}')
    write_page((b for b in cur_releases if b.format.is_digital()),
                DIGITAL, f'# Digital {title}')
    write_page((b for b in cur_releases if b.format.is_physical()),
                PHYSICAL, f'# Physical {title}')
    write_page((b for b in cur_releases if b.format == Format.AUDIOBOOK),
                AUDIOBOOK, f'# Audiobook {title}')

    YEAR.mkdir(exist_ok=True)
    for file in YEAR.iterdir():
        file.unlink()
    start = 0
    while start < len(releases):
        year = releases[start].date.year
        end_date = datetime.datetime(year, 12, 31).date()
        end = bisect_right(releases, end_date, key=attrgetter('date'), lo=start)
        write_page(releases[start:end], YEAR/f'{year}.md', f'# {year} {title}')
        start = end


if __name__ == '__main__':
    main()
