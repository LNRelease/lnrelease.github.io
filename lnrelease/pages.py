import datetime
import json
from bisect import bisect_right
from operator import attrgetter
from pathlib import Path

from scrape import SERIES
from utils import Format, Series, Table
from write import get_current, get_releases, write_page

HTML = Path('html.md')
DIGITAL = Path('digital.md')
PHYSICAL = Path('physical.md')
AUDIOBOOK = Path('audiobook.md')
YEAR = Path('year')
DATA = Path('data.json')


def main() -> None:
    releases = get_releases()
    current = get_current(releases)

    title = 'Light Novel Releases'
    write_page((b for b in current if b.format != Format.AUDIOBOOK),
               HTML, f'# Licensed {title}')
    write_page((b for b in current if b.format.is_digital()),
               DIGITAL, f'# Digital {title}')
    write_page((b for b in current if b.format.is_physical()),
               PHYSICAL, f'# Physical {title}')
    write_page((b for b in current if b.format == Format.AUDIOBOOK),
               AUDIOBOOK, f'# Audiobook {title}')

    YEAR.mkdir(exist_ok=True)
    start = 0
    while start < len(releases):
        year = releases[start].date.year
        end_date = datetime.datetime(year, 12, 31).date()
        end = bisect_right(releases, end_date, key=attrgetter('date'), lo=start)
        write_page(releases[start:end], YEAR/f'{year}.md', f'# {year} {title}')
        start = end

    releases.sort(key=lambda x: x.serieskey)
    table = {x.key: x.title for x in Table(SERIES, Series)}
    series = {x: i for i, x in enumerate(sorted({x.serieskey for x in releases}))}
    publishers = {x: i for i, x in enumerate(sorted({x.publisher for x in releases}))}
    formats = {x: i for i, x in enumerate(Format)}
    jsn = {'series': [[key, table[key]] for key in series],
           'publishers': list(publishers),
           'data': [[series[x.serieskey],
                x.link,
                publishers[x.publisher],
                x.name,
                x.volume,
                formats[x.format],
                x.isbn,
                str(x.date),
                ] for x in releases]}
    with open(DATA, 'w') as file:
        json.dump(jsn, file, separators=(',', ':'))


if __name__ == '__main__':
    main()
