import datetime
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable
from operator import attrgetter
from pathlib import Path

from parse import BOOKS
from utils import FORMATS, Book, Format, Release, Table

OUT = Path('README.md')


def get_format(format: Format, github: bool) -> str:
    if github:
        return str(format)
    elif format == Format.DIGITAL:
        return f'{format}<span class="hidden">{Format.PHYSICAL}</span>'
    elif format == Format.PHYSICAL:
        return f'<span class="hidden">{Format.DIGITAL}</span>{format}'
    return str(format)


def write_page(releases: Iterable[Release], output: Path, title: str, github: bool = False) -> None:
    with open(output, 'w', encoding='utf-8') as file:
        month = 0
        year = 0
        file.write(title)
        if not github:
            file.write('\n\n- toc\n{:toc}')
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

            date = release.date.strftime('%b %d')
            name = f'[{release.name}]({release.link} "{release.publisher}")'
            format = get_format(release.format, github)
            file.write(f'{date}|{name}|{release.volume}|{release.publisher}|{format}|\n')


def get_releases() -> list[Release]:
    dic: defaultdict[Release, list[Book]] = defaultdict(list)
    for book in sorted(Table(BOOKS, Book)):
        dic[Release(*book)].append(book)
    for release, books in dic.items():
        books.sort(key=lambda b: FORMATS.get(b.format, 0))
        formats = {Format.from_str(b.format) for b in books}
        release.format = formats.pop() if len(formats) == 1 else Format.PHYSICAL_DIGITAL
        release.link = books[0].link
        release.isbn = books[0].isbn
    return sorted(dic)


def get_current(releases: list[Release]) -> tuple[int, int]:
    today = datetime.datetime.today()
    start_date = today - datetime.timedelta(days=7)
    start_date = start_date.replace(day=1).date()
    end_date = today.replace(year=today.year+1, month=12, day=31).date()
    start = bisect_left(releases, start_date, key=attrgetter('date'))
    end = bisect_right(releases, end_date, key=attrgetter('date'), lo=start)
    return releases[start:end]


def main() -> None:
    releases = get_releases()
    current = get_current(releases)
    write_page((b for b in current if b.format != Format.AUDIOBOOK),
               OUT, f'# Licensed Light Novel Releases', True)


if __name__ == '__main__':
    main()
