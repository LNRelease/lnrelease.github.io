import importlib
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from utils import Info, Series, Table

SOURCES = [importlib.import_module(f'source.{s.stem}') for s in Path('lnrelease/source').glob('*.py')]

SERIES = Path('series.csv')
INFO = Path('info.csv')


def main() -> None:
    series = Table(SERIES, Series)
    info = Table(INFO, Info)
    sources: defaultdict[str, set[Info]] = defaultdict(set)
    for inf in info:
        sources[inf.source].add(inf)

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(s.scrape_full, series.copy(), sources[s.NAME].copy()): s.NAME for s in SOURCES}
        for future in as_completed(futures):
            try:
                serie, inf = future.result()
                series |= serie
                series.save()
                info -= sources[futures[future]]
                info |= inf
                info.save()
            except Exception as e:
                warnings.warn(f'Error scraping {futures[future]}: {e}', RuntimeWarning)
            else:
                print(f'{futures[future]} done')

    series -= series - {Series(i.serieskey, '') for i in info}
    series.save()


if __name__ == '__main__':
    main()
