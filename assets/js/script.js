const COLUMNS = 5;
const CHUNK_SIZE = 512;
const GROUP_THRESHOLD = 40;
const YEAR_THRESHOLD = 24;
const SEARCH_THRESHOLD = 800;

const HEADER_HEIGHT = 32;
const GROUP_HEIGHT = 28;

const PHYSICAL = 1;
const DIGITAL = 2;
const PHYSICAL_DIGITAL = 3;
const AUDIOBOOK = 4;

const SHOWN = document.getElementById('shown');
const TOTAL = document.getElementById('total');
const SEARCH = document.getElementById('search');
const TABLE = document.getElementById('table');
const HEADERS = Array.from(document.getElementById('headers').children);
const ROWS = document.getElementById('rows');
const PAD = document.getElementById('pad');
const CALC = document.getElementById('calc');
const LOADING = document.getElementById('loading');
const STAR = document.getElementById('star');
const STARS = document.getElementById('stars');

const COLLATOR = new Intl.Collator();
const VOL_COMPARATOR = (a, b) => {
    const af = parseFloat(a);
    const bf = parseFloat(b);
    return isNaN(af) || isNaN(bf) ? COLLATOR.compare(a, b) : af - bf;
};
const COMPARATORS = [
    (a, b) => a.time - b.time,
    (a, b) => COLLATOR.compare(a.title, b.title),
    (a, b) => VOL_COMPARATOR(a.volume, b.volume),
    (a, b) => COLLATOR.compare(a.publisher, b.publisher),
    (a, b) => a.format - b.format,
    // reversed
    (a, b) => b.time - a.time,
    (a, b) => COLLATOR.compare(b.title, a.title),
    (a, b) => VOL_COMPARATOR(b.volume, a.volume),
    (a, b) => COLLATOR.compare(b.publisher, a.publisher),
    (a, b) => b.format - a.format,
];

const GROUP_FORMAT = new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'long',
});

const storage = (() => {
    try {
        const test = '__test__';
        window.localStorage.setItem(test, test);
        window.localStorage.removeItem(test);
        return window.localStorage;
    } catch {
        return null;
    }
})();
const settings = JSON.parse(storage?.getItem('settings')) || {};
// Set defaults
settings.order ??= 0;
settings.star ??= false;
settings.series ??= [];
settings.publisher ??= [];
settings.format ??= [PHYSICAL, DIGITAL, PHYSICAL_DIGITAL];
storage?.setItem('settings', JSON.stringify(settings));

// Scroll when novels loaded
let hashFragment = window.location.hash.substring(1) || null;

function dateFilter() {
    const now = new Date();
    const endTime = Date.UTC(now.getFullYear() + 1, 11, 31);
    now.setDate(now.getDate() - 7);
    now.setDate(1);
    const startTime = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    return { start: startTime, end: endTime };
}

function norm(s) {
    return s.normalize('NFKD').replace(/[^\w\s]/g, '').toLowerCase();
}

function yieldTask() {
    return new Promise(resolve => setTimeout(resolve));
}


class Novels extends Array {
    constructor(series, publishers) {
        super();
        this.filters = {
            date: dateFilter(),
            star: new Set(settings.series),
            volume: { start: '', end: '' },
            publisher: new Set(publishers.filter(item =>
                !settings.publisher.includes(item))),
            format: new Set(settings.format),
        };
        this.shown = 0;
        this.order = settings.order;
        this.grouped = this.order % COLUMNS === 0;
        this.publishers = publishers;
        this.series = new Map(series);
        this.normSeries = undefined;
        this.stars = new Map();

        this.widths = undefined;
        this.updater = undefined;
        this.rows = undefined;
        this.groups = undefined;
        this.heights = undefined;
        this.rowStart = -1;
        this.rowEnd = -1;
    }

    add(item, series, publishers) {
        const book = new Book(item, series, publishers, this.filters);
        this.push(book);
        if (book.filter) {
            this.shown++;
            book.show = true;
        }
    }

    static get [Symbol.species]() { return Array; }
}

class Book {
    constructor(item, series, publishers, filters) {
        [this.serieskey, this.series] = series[item[0]];
        this.link = item[1];
        this.publisher = publishers[item[2]];
        this.title = item[3];
        this.volume = item[4];
        this.format = item[5];
        this.isbn = item[6];
        this.date = item[7];
        const date = new Date(this.date);
        this.time = date.getTime();
        this.group = GROUP_FORMAT.format(date);
        this.year = this.date.substring(0, 4);
        this.id = this.date.substring(0, 7);
        this.show = false;
        this.filter = true;
        this.filters = {
            date: true,
            title: true,
            star: true,
            volume: true,
            publisher: true,
            format: true,
        };
        this.filterDate(filters.date);
        this.filterStar(filters.star);
        this.filterVolume(filters.volume);
        this.filterPublisher(filters.publisher);
        this.filterFormat(filters.format);
        this.row = undefined;
        this.pad = undefined;
        this.dark = false;
        this.normSeries = undefined;
        this.normTitle = undefined;
        this.search = undefined;
    }

    norm(series) { // Takes a little time
        this.normSeries = series.get(this.serieskey);
        this.normTitle = norm(this.title);
        let format;
        switch (this.format) {
            case PHYSICAL:
                format = 'physical';
                break;
            case DIGITAL:
                format = 'digital';
                break;
            case PHYSICAL_DIGITAL:
                format = 'physical|digital';
                break;
            case AUDIOBOOK:
                format = 'audiobook';
                break;
        }
        this.search = `${this.normTitle}|${this.normSeries}|${this.volume}|${format}`;
    }

    filterDate(filter) {
        const old = this.filters.date;
        this.filters.date = (!filter.start || filter.start <= this.time)
            && (!filter.end || this.time <= filter.end);
        if (old !== this.filters.date)
            this.filter = !old && this.getFilter();
    }

    filterStar(filter) {
        const old = this.filters.star;
        this.filters.star = filter.has(this.serieskey);
        if (old !== this.filters.star && settings.star)
            this.filter = this.getFilter();
    }

    filterVolume(filter) {
        const old = this.filters.volume;
        this.filters.volume =
            (!filter.start
                || VOL_COMPARATOR(filter.start, this.volume) <= 0)
            && (!filter.end
                || VOL_COMPARATOR(this.volume, filter.end) <= 0);
        if (old !== this.filters.volume)
            this.filter = !old && this.getFilter();
    }

    filterPublisher(filter) {
        const old = this.filters.publisher;
        this.filters.publisher = filter.has(this.publisher);
        if (old !== this.filters.publisher)
            this.filter = !old && this.getFilter();
    }

    filterFormat(filter) {
        const old = this.filters.format;
        this.filters.format = filter.has(this.format);
        if (old !== this.filters.format)
            this.filter = !old && this.getFilter();
    }

    getFilter() {
        return this.filters.date
            && this.filters.title
            && (!settings.star || this.filters.star)
            && this.filters.volume
            && this.filters.publisher
            && this.filters.format;
    }
}

function setWidths(volumes, publishers) {
    const rows = [];
    const len = Math.max(volumes.length, publishers.length);
    for (let i = 0; i < len; i++) {
        const volume = volumes[i];
        const publisher = publishers[i];

        const row = document.createElement('div');
        row.classList.add('row');
        const date = document.createElement('div');
        date.textContent = '0000-00-00';
        const title = document.createElement('div');
        title.style.width = '100%';
        const vol = document.createElement('div');
        vol.textContent = volume;
        const pub = document.createElement('div');
        pub.textContent = publisher;
        pub.style.display = 'table-cell';
        const format = document.createElement('div');
        format.textContent = '🖥️📖';
        row.append(date, title, vol, pub, format);
        rows.push(row);
    }
    ROWS.append(...rows);
    HEADERS[1].style.width = '100%';

    const widths = [];
    for (let i = 0; i < COLUMNS; i++) {
        if (i === 1) {
            widths.push(null);
            continue;
        }
        const rect = HEADERS[i].getBoundingClientRect();
        let width = rect.right - rect.left;
        for (const row of rows) {
            const r = row.children[i].getBoundingClientRect();
            width = Math.max(width, r.right - r.left);
        }
        widths.push(width + 'px');
    }

    const pad = PAD.children;
    for (const [i, width] of widths.entries()) {
        HEADERS[i].style.width = width;
        pad[i].style.width = width;
    }
    return widths;
}

function initNovels(series, publishers, data) {
    const novels = new Novels(series, publishers);
    const start = new Date(novels.filters.date.start)
        .toISOString().substring(0, 10);
    const end = new Date(novels.filters.date.end)
        .toISOString().substring(0, 10);
    const todo = [];
    const volWidths = [];
    for (const [i, item] of data.entries()) {
        const vol = item[4];
        const len = vol.length;
        const big = volWidths[0]?.length || 0;
        if (len > big) {
            volWidths[0] = vol;
            volWidths.length = 1;
        } else if (len == big) {
            volWidths.push(vol);
        }

        const date = item[7];
        (start > date || date > end) ? todo.push(i)
            : novels.add(item, series, publishers);
    }
    const pubWidths = [];
    for (const pub of publishers) {
        const len = pub.length;
        const big = pubWidths[0]?.length || 0;
        if (len > big) {
            pubWidths[0] = pub;
            pubWidths.length = 1;
        } else if (len == big) {
            pubWidths.push(pub);
        }
    }
    novels.widths = setWidths(volWidths, pubWidths);
    novels.sort(COMPARATORS[novels.order]);
    HEADERS[novels.order % COLUMNS].classList.add(
        novels.order < COLUMNS ? 'sort-desc' : 'sort-asc');
    TOTAL.textContent = data.length;

    return [novels, todo];
}

function getRow(book, widths) {
    if (book.row) {
        book.row.classList.toggle('row-dark', book.dark);
        return book.row;
    }

    const date = document.createElement('div');
    date.style.width = widths[0];
    date.textContent = book.date;

    const title = document.createElement('div');
    title.title = book.publisher;
    const a = document.createElement('a');
    a.href = book.link;
    a.textContent = book.title;
    const star = document.createElement('span');
    star.title = '';
    star.dataset.series = book.serieskey;
    star.classList.add('star', 'star-btn',
        book.filters.star ? 'star-active' : null);
    title.append(a, star);

    const volume = document.createElement('div');
    volume.style.width = widths[2];
    volume.textContent = book.volume;

    const publisher = document.createElement('div');
    publisher.style.width = widths[3];
    publisher.textContent = book.publisher;

    const format = document.createElement('div');
    format.style.width = widths[4];
    format.title = book.isbn;
    switch (book.format) {
        case PHYSICAL: {
            const span = document.createElement('span');
            span.className = 'hidden';
            span.textContent = '🖥️';
            format.append(span, '📖');
            break;
        } case DIGITAL: {
            const span = document.createElement('span');
            span.className = 'hidden';
            span.textContent = '📖';
            format.append('🖥️', span);
            break;
        } case PHYSICAL_DIGITAL: {
            format.textContent = '🖥️📖';
            break;
        } case AUDIOBOOK: {
            format.textContent = '🔊';
            break;
        }
    }

    book.row = document.createElement('div');
    book.row.classList.add('row');
    book.row.classList.toggle('row-dark', book.dark);
    book.row.append(date, title, volume, publisher, format);
    return book.row;
}

function getPad(book) {
    if (book.pad)
        return book.pad;

    book.pad = document.createElement('div');
    book.pad.classList.add('pad-row');
    book.pad.textContent = book.title;
    return book.pad;
}

function getGroup(month, id) {
    const row = document.createElement('div');
    row.classList.add('row', 'sticky', 'group');
    row.id = id;
    const div = document.createElement('div');
    div.textContent = month;
    row.append(div);
    return row;
}

function findRow(heights, target, start = 0, end = heights.length, mod = 0) {
    let low = start;
    let high = end - 1;

    while (low < high) {
        const mid = (low + high) >> 1;
        if (heights[mid] > target)
            high = mid;
        else
            low = mid + 1;
    }
    return Math.min(Math.max(low + mod, 0), heights.length - 1);
}

function findGroup(groups, target) {
    let low = 0;
    let high = groups.length - 1;

    while (low < high) {
        const mid = (low + high) >> 1;
        const val = groups[mid];
        if (val === target)
            return undefined;
        else if (val < target)
            low = mid + 1;
        else
            high = mid;
    }
    return groups[low - 1];
}

function drawTable(novels) {
    if (novels.updater)
        return;

    const rows = novels.rows;
    const groups = novels.groups;
    const heights = novels.heights;
    const widths = novels.widths;

    const scrollTop = window.scrollY;
    const clientHeight = document.documentElement.clientHeight;
    const scrollBottom = scrollTop + clientHeight;
    const rowsTop = ROWS.offsetTop;

    const rowStart = findRow(heights, scrollTop - rowsTop, 0, rows.length, -1);
    const rowEnd = findRow(heights, scrollBottom - rowsTop, rowStart, rows.length, 1);

    if (rowStart > novels.rowEnd || novels.rowStart > rowEnd) {
        const group = rows[findGroup(groups, rowStart)];
        ROWS.replaceChildren(PAD);
        if (group) ROWS.prepend(group);

        for (let i = rowStart; i < rowEnd; i++) {
            const row = rows[i];
            ROWS.append(row instanceof Book ? getRow(row, widths) : row);
        }
    } else {
        const startChange = rowStart - novels.rowStart;
        const endChange = rowEnd - novels.rowEnd;

        if (startChange > 0) {
            let group;
            for (let i = novels.rowStart; i < rowStart; i++) {
                const row = rows[i];
                if (row instanceof Book) {
                    getRow(row, widths).remove();
                } else {
                    row.remove();
                    group = row;
                }
            }
            if (group) {
                const first = ROWS.firstChild;
                first !== PAD ? first.replaceWith(group)
                    : ROWS.prepend(group);
            }
        } else if (startChange < 0) {
            let makeGroup = false;
            for (let i = novels.rowStart; i > rowStart;) {
                const row = rows[--i];
                if (row instanceof Book) {
                    PAD.after(getRow(row, widths));
                } else {
                    PAD.after(row);
                    makeGroup = true;
                }
            }
            if (makeGroup) {
                const group = rows[findGroup(groups, rowStart - 1)];
                if (group) ROWS.prepend(group);
            }
        }

        if (endChange > 0) {
            for (let i = novels.rowEnd; i < rowEnd; i++) {
                const row = rows[i];
                ROWS.append(row instanceof Book ? getRow(row, widths) : row);
            }
        } else if (endChange < 0) {
            for (let i = novels.rowEnd; i > rowEnd;) {
                const row = rows[--i];
                (row instanceof Book ? getRow(row, widths) : row).remove();
            }
        }
    }
    const groupHeight = ROWS.firstChild === PAD ? 0 : GROUP_HEIGHT;
    PAD.style.height = heights[rowStart] - groupHeight + 'px';
    novels.rowStart = rowStart;
    novels.rowEnd = rowEnd;
}

async function redrawTable(novels) {
    const updater = {};
    novels.updater = updater;

    PAD.style.minHeight = null;
    LOADING.style.display = 'block';
    SHOWN.textContent = novels.shown;
    ROWS.replaceChildren(PAD);

    novels.rowStart = -1;
    novels.rowEnd = -1;
    novels.heights = [0];
    let height = 0;
    const children = [];
    for (const [i, row] of novels.rows.entries()) {
        if (i && i % CHUNK_SIZE === 0) {
            CALC.replaceChildren(...children);
            for (const child of children)
                novels.heights.push(height += child.offsetHeight);
            children.length = 0;
            CALC.replaceChildren();
            await yieldTask();
            if (novels.updater !== updater)
                return;
        }
        children.push(row instanceof Book ? getPad(row) : row);
    }
    CALC.replaceChildren(...children);
    for (const child of children)
        novels.heights.push(height += child.offsetHeight);
    novels.updater = undefined;

    drawTable(novels);
    CALC.replaceChildren();
    LOADING.style.display = null;
    TABLE.style.height = height + HEADER_HEIGHT + 'px';
}

function initListeners(novels) {
    document.addEventListener('scroll', () => drawTable(novels));
    let width = TABLE.offsetWidth;
    window.addEventListener('resize', () => {
        const newWidth = TABLE.offsetWidth;
        if (newWidth !== width) {
            redrawTable(novels);
            width = newWidth;
        } else {
            drawTable(novels);
        }
    });
}

function checkGroups(rows, groups, count, year) {
    if (count <= YEAR_THRESHOLD && groups.length) {
        for (const [i, group] of groups.entries()) {
            i ? rows.delete(group)
                : rows.get(group).firstChild.textContent = year;
        }
    }
}

async function rebuildTable(novels, group = null) {
    let i = 0;
    let groupStart, groupName, groups, year;
    const rows = new Map();
    group ??= novels.grouped;
    novels.grouped = group;
    group &= novels.shown > GROUP_THRESHOLD;

    novels.shown = 0;
    for (const book of novels) {
        if (!book.show)
            continue;

        if (group && groupName !== book.group) {
            if (year !== book.year) {
                checkGroups(rows, groups, i - groupStart, year);
                groupStart = i;
                year = book.year;
                groups = [];
            }
            groupName = book.group;
            groups.push(i);
            rows.set(i++, getGroup(book.group, book.id));
        }
        rows.set(i++, book);
        novels.shown++;
    }
    checkGroups(rows, groups, i - groupStart, year);

    novels.rows = [];
    novels.groups = [];
    let dark = false;
    for (const row of rows.values()) {
        if (row instanceof Book) {
            row.dark = dark;
            dark = !dark;
        } else {
            novels.groups.push(novels.rows.length);
            dark = false;
        }
        novels.rows.push(row);
    }
    await redrawTable(novels);
}

function sortTable(novels, index) {
    const newOrder = novels.order === index ? index + COLUMNS : index;
    novels.sort(COMPARATORS[newOrder]);
    rebuildTable(novels, index === 0);

    HEADERS[novels.order % COLUMNS].classList.remove('sort-desc', 'sort-asc');
    const newClasses = HEADERS[index].classList;
    if (newOrder < COLUMNS) {
        newClasses.remove('sort-asc');
        newClasses.add('sort-desc');
    } else {
        newClasses.remove('sort-desc');
        newClasses.add('sort-asc');
    }
    novels.order = newOrder;
}

function initSort(novels) {
    for (const [i, th] of HEADERS.entries()) {
        th.addEventListener('click', e => {
            if (e.target === th)
                sortTable(novels, i);
        });
    }
}

function searchBook(book, include, exclude) {
    for (const word of exclude) {
        if (book.search.includes(word))
            return false;
    }
    for (const word of include) {
        if (!book.search.includes(word))
            return false;
    }
    return true;
}

function filterTable(novels) {
    const search = SEARCH.value;
    if (search) {
        const include = [];
        const exclude = [];
        for (const word of search.matchAll(/(?<!\S)(?:-?".+"|\S+)(?!\S)/g)) {
            const normWord = norm(word[0]);
            if (normWord)
                (word[0][0] === '-' ? exclude : include).push(normWord);
        }
        for (const book of novels)
            book.show = searchBook(book, include, exclude);
        if (novels.shown > SEARCH_THRESHOLD) {
            for (const book of novels) {
                if (book.show && !book.filter)
                    book.show = false;
            }
        }
    } else {
        for (const book of novels)
            book.show = book.filter;
    }
    rebuildTable(novels);
}

function createStar(novels, serieskey, series) {
    const div = document.createElement('div');
    div.classList.add('list-row');
    const text = document.createElement('span');
    text.textContent = series;
    text.classList.add('row-text');
    const btn = document.createElement('span');
    btn.classList.add('menu-btn', 'cross');
    btn.addEventListener('click', e => {
        e.stopPropagation();
        unstarSeries(novels, serieskey, div);
    });
    div.append(text, btn);
    let next;
    for (const [key, value] of novels.stars) {
        if (serieskey < key) {
            next = value;
            break;
        }
    }
    next ? STARS.insertBefore(div, next) : STARS.append(div);
    novels.stars.set(serieskey, div);
}

function starSeries(novels, serieskey, series) {
    novels.filters.star.add(serieskey);
    for (const book of novels) {
        if (book.serieskey === serieskey) {
            book.filters.star = true;
            if (settings.star) book.filter = book.getFilter();
            book.row?.querySelector('.star-btn')
                .classList.add('star-active');
        }
    }
    if (settings.star) filterTable(novels);
    createStar(novels, serieskey, series);
}

function unstarSeries(novels, serieskey, div) {
    novels.stars.delete(serieskey);
    novels.filters.star.delete(serieskey);
    for (const book of novels) {
        if (book.serieskey === serieskey) {
            book.filters.star = false;
            if (settings.star) book.filter = false;
            book.row?.querySelector('.star-btn')
                .classList.remove('star-active');
        }
    }
    if (settings.star) filterTable(novels);
    div.remove();
}

function initDate(novels) {
    const header = HEADERS[0].classList;
    const start = document.getElementById('date-start');
    const end = document.getElementById('date-end');
    const dates = novels.filters.date;
    if (dates.start) {
        start.value = new Date(dates.start)
            .toISOString().substring(0, 10);
        header.add('filter');
    }
    if (dates.end) {
        end.value = new Date(dates.end)
            .toISOString().substring(0, 10);
        header.add('filter');
    }

    document.getElementById('date-reset')
        .addEventListener('click', () => {
            novels.filters.date = dateFilter();
            const filter = novels.filters.date;
            start.value = new Date(filter.start)
                .toISOString().substring(0, 10);
            end.value = new Date(filter.end)
                .toISOString().substring(0, 10);
            for (const book of novels)
                book.filterDate(filter);
            filterTable(novels);
            header.add('filter');
        });

    function filter(event) {
        const filter = novels.filters.date;
        const target = event.target;
        filter[target.name] = new Date(target.value).getTime() || null;
        for (const book of novels)
            book.filterDate(filter);
        filterTable(novels);
        header.toggle('filter', filter.start || filter.end);
    }

    start.addEventListener('input', filter);
    end.addEventListener('input', filter);
}

function initTitle(novels) {
    HEADERS[1].querySelector('.sort-btn').addEventListener('click',
        () => document.getElementById('series')
            .replaceChildren(...Array.from(novels.series.values(),
                series => new Option(series))), { once: true });
    const header = HEADERS[1].classList;
    const search = document.getElementById('filter-search');
    const plus = document.getElementById('star-add');
    if (search.value || settings.star) header.add('filter');

    search.addEventListener('input', () => {
        const value = search.value;
        const normValue = norm(value);
        const key = novels.normSeries.get(normValue);
        if (key) {
            for (const book of novels) {
                const old = book.filters.title;
                book.filters.title = key === book.serieskey;
                if (old !== book.filters.title)
                    book.filter = !old && book.getFilter();
            }
        } else {
            let regex;
            try {
                regex = new RegExp(value, 'i');
            } catch {
                if (!normValue) return; // Probably writing a regex
                regex = new RegExp(normValue, 'i');
            }
            for (const book of novels) {
                const old = book.filters.title;
                book.filters.title = regex.test(book.series)
                    || regex.test(book.title)
                    || regex.test(book.normSeries)
                    || regex.test(book.normTitle);
                if (old !== book.filters.title)
                    book.filter = !old && book.getFilter();
            }
        }
        filterTable(novels);
        plus.classList.toggle('disabled', !key);
        header.toggle('filter', value);
    });
    plus.addEventListener('click', () => {
        const key = novels.normSeries.get(norm(search.value));
        if (key) starSeries(novels, key, novels.series.get(key));
    });

    STAR.checked = settings.star;
    STAR.addEventListener('change', () => {
        settings.star = STAR.checked;
        for (const book of novels)
            book.filter = !settings.star ? book.getFilter()
                : book.filter && book.filters.star;
        filterTable(novels);
        header.toggle('filter', settings.star);
    });
    for (const key of settings.series) {
        const series = novels.series.get(key);
        if (series) createStar(novels, key, series);
    }

    document.getElementById('title-reset')
        .addEventListener('click', () => {
            if (!window.confirm('Reset all starred series?'))
                return;

            search.value = '';
            STAR.checked = false;
            settings.star = false;
            for (const book of novels) {
                if (!book.filters.title || book.filters.star) {
                    book.filters.title = true;
                    book.filters.star = false;
                    book.filter = book.getFilter();
                    book.row?.querySelector('.star-btn')
                        .classList.remove('star-active');
                }
            }
            filterTable(novels);
            header.remove('filter');
            for (const row of novels.stars.values())
                row.remove();
            novels.filters.star.clear();
            novels.stars.clear();
        });
}

function initVolume(novels) {
    const header = HEADERS[2].classList;
    const start = document.getElementById('vol-start');
    const end = document.getElementById('vol-end');
    if (start.value || end.value) header.add('filter');
    document.getElementById('vol-reset')
        .addEventListener('click', () => {
            start.value = '';
            end.value = '';
            const filter = novels.filters.volume;
            filter.start = '';
            filter.end = '';
            for (const book of novels)
                book.filterVolume(filter);
            filterTable(novels);
            header.remove('filter');
        });
    function filter(event) {
        const filter = novels.filters.volume;
        const target = event.target;
        filter[target.name] = target.value.trim();
        for (const book of novels)
            book.filterVolume(filter);
        filterTable(novels);
        header.toggle('filter', filter.start || filter.end);
    }
    start.addEventListener('input', filter);
    end.addEventListener('input', filter);
}

function initPublisher(novels) {
    const header = HEADERS[3].classList;
    const select = document.getElementById('pub-select').classList;
    const menu = document.getElementById('menu-pub');

    let checked = false;
    let filter = false;
    const boxes = novels.publishers.map(publisher => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.name = 'publishers';
        checkbox.value = publisher;
        checkbox.defaultChecked = true;

        const check = novels.filters.publisher.has(publisher);
        checked |= check;
        filter |= !check;
        checkbox.checked = check;
        label.append(checkbox, publisher);
        menu.append(label);
        checkbox.addEventListener('change', e => {
            const checked = e.target.checked;
            checked ? novels.filters.publisher.add(publisher)
                : novels.filters.publisher.delete(publisher);
            for (const book of novels) {
                if (book.publisher === publisher
                    && book.filters.publisher !== checked) {
                    book.filters.publisher = checked;
                    book.filter = checked && book.getFilter();
                }
            }
            filterTable(novels);
            select.toggle('check', boxes.some(box => box.checked));
            header.toggle('filter', boxes.some(box => !box.checked));
        });
        return checkbox;
    });

    if (filter) header.add('filter');
    if (checked) select.add('check');
    document.getElementById('pub-select')
        .addEventListener('click', () => {
            const b = !select.contains('check');
            for (const box of boxes)
                box.checked = b;
            b ? novels.filters.publisher = new Set(novels.publishers)
                : novels.filters.publisher.clear();
            for (const book of novels) {
                if (b !== book.filters.publisher) {
                    book.filters.publisher = b;
                    book.filter = b && book.getFilter();
                }
            }
            filterTable(novels);
            select.toggle('check');
            header.toggle('filter', !b);
        });
    document.getElementById('pub-reset')
        .addEventListener('click', () => {
            for (const box of boxes)
                box.checked = true;
            novels.filters.publisher = new Set(novels.publishers);
            for (const book of novels) {
                if (!book.filters.publisher) {
                    book.filters.publisher = true;
                    book.filter = book.getFilter();
                }
            }
            filterTable(novels);
            select.add('check');
            header.remove('filter');
        });
}

function initFormat(novels) {
    const header = HEADERS[4].classList;
    const menu = document.getElementById('menu-format');
    const select = document.getElementById('format-select').classList;

    let checked = false;
    let filter = false;
    const boxes = Array.prototype.map.call(
        menu.querySelectorAll('input[name="format"]'), box => {
            let format;
            switch (box.value) {
                case 'physical':
                    format = PHYSICAL;
                    break;
                case 'digital':
                    format = DIGITAL;
                    break;
                case 'physical-digital':
                    format = PHYSICAL_DIGITAL;
                    break;
                case 'audiobook':
                    format = AUDIOBOOK;
                    break;
            }
            const check = novels.filters.format.has(format);
            checked |= check;
            filter |= !check;
            box.checked = check;

            box.addEventListener('change', e => {
                const checked = e.target.checked;
                checked ? novels.filters.format.add(format)
                    : novels.filters.format.delete(format);
                for (const book of novels) {
                    if (book.format === format
                        && book.filters.format !== checked) {
                        book.filters.format = checked;
                        book.filter = checked && book.getFilter();
                    }
                }
                filterTable(novels);
                select.toggle('check', boxes.some(box => box[0].checked));
                header.toggle('filter', boxes.some(box => !box[0].checked));
            });
            return [box, format];
        });

    if (filter) header.add('filter');
    if (checked) select.add('check');
    document.getElementById('format-select')
        .addEventListener('click', () => {
            const b = !select.contains('check');
            for (const [box, _] of boxes)
                box.checked = b;
            b ? novels.filters.format = new Set(boxes.map(a => a[1]))
                : novels.filters.format.clear();
            for (const book of novels) {
                if (b !== book.filters.format) {
                    book.filters.format = b;
                    book.filter = b && book.getFilter();
                }
            }
            filterTable(novels);
            select.toggle('check');
            header.toggle('filter', !b);
        });
    document.getElementById('format-reset')
        .addEventListener('click', () => {
            const filter = novels.filters.format;
            let tick = false;
            for (const [box, format] of boxes) {
                const b = box.defaultChecked;
                tick |= b;
                box.checked = b;
                b ? filter.add(format) : filter.delete(format);
            }
            for (const book of novels)
                book.filterFormat(filter);
            filterTable(novels);
            select.toggle('check', filter);
            header.toggle('filter', boxes.some(box => !box[0].checked));
        });
}

function initMenus() {
    const closers = Array.prototype.map.call(HEADERS, th => {
        const div = th.querySelector('.sort-btn');
        const filter = th.querySelector('.sort-menu');
        function closeFilter(e = null) {
            if (e && (
                e.type === 'click' && th.contains(e.target)
                || e.type === 'keydown' && e.key !== 'Escape'))
                return;
            document.removeEventListener('click', closeFilter);
            document.removeEventListener('keydown', closeFilter);
            filter.style.right = null;
            filter.style.top = null;
            th.classList.remove('menu-active');
        }

        function placeFilter(filter, e) {
            const clientWidth = document.documentElement.clientWidth;
            const tableRect = TABLE.getBoundingClientRect();
            const thRect = th.getBoundingClientRect();
            const filterX = filter.offsetWidth;
            let x, y;
            if (e.type === 'contextmenu') {
                x = thRect.right - e.clientX - Math.ceil(filterX / 2);
                y = e.clientY - thRect.top + 'px';
            } else {
                x = 0;
                y = '2em';
            }

            // Constrain to table
            x -= Math.min(tableRect.right - thRect.right + x, 0);
            x += Math.min(thRect.right - x - filterX - tableRect.left, 0);
            // Constrain to page 
            x -= Math.min(clientWidth - thRect.right + x, 0);
            x += Math.min(thRect.right - x - filterX, 0);
            filter.style.right = x + 'px';
            filter.style.top = y;
        }

        function openFilter(e) {
            const classes = th.classList;
            if (!classes.contains('menu-active')) {
                for (const closer of closers) {
                    if (closer !== closeFilter)
                        closer();
                }
                classes.add('menu-active');
                document.addEventListener('click', closeFilter);
                document.addEventListener('keydown', closeFilter);
            }
            placeFilter(filter, e);
        }

        function toggleFilter(e) {
            if (th.classList.contains('menu-active')) {
                for (const close of closers) {
                    close();
                }
            } else {
                openFilter(e);
            }
        }
        div.addEventListener('click', toggleFilter);
        th.addEventListener('contextmenu', e => {
            if (filter.contains(e.target))
                return;
            openFilter(e);
            e.preventDefault();
        });
        return closeFilter;
    });
}

function initFilter(novels) {
    initDate(novels);
    initTitle(novels);
    initVolume(novels);
    initPublisher(novels);
    initFormat(novels);
    initMenus();

    function toggleStar(target) {
        const serieskey = target.dataset.series;
        target.classList.contains('star-active') ?
            unstarSeries(novels, serieskey, novels.stars.get(serieskey))
            : starSeries(novels, serieskey, novels.series.get(serieskey));
    }

    ROWS.addEventListener('click', e => {
        const target = e.target;
        if (target.classList.contains('star-btn'))
            toggleStar(e.target);
    });
    ROWS.addEventListener('contextmenu', e => {
        const target = e.target;
        if (target.parentNode.firstChild === target)
            return;
        const star = target.closest('.row').querySelector('.star-btn');
        if (star) {
            toggleStar(star);
            e.preventDefault();
        }
    });
    if (storage) { // Save on exit
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                Object.keys(settings).forEach(key => delete settings[key]);
                settings.order = novels.order;
                settings.star = STAR.checked;
                settings.series = Array.from(novels.filters.star).sort();
                settings.publisher = novels.publishers.filter(item =>
                    !novels.filters.publisher.has(item));
                settings.format = Array.from(novels.filters.format);
                storage.setItem('settings', JSON.stringify(settings));
            }
        });
    }
}

function initSearch(novels) {
    SEARCH.addEventListener('input', () =>
        filterTable(novels));
}

async function init() {
    const response = await fetch('data.json');
    const { series, publishers, data } = await response.json();

    const [novels, todo] = initNovels(series, publishers, data);
    initListeners(novels);
    await rebuildTable(novels);
    await yieldTask();

    for (const i of todo)
        novels.add(data[i], series, publishers);
    novels.sort(COMPARATORS[novels.order]);
    await yieldTask();

    const map = new Map();
    for (const [key, name] of novels.series)
        map.set(key, norm(name));
    for (const book of novels)
        book.norm(map);
    novels.normSeries = new Map();
    for (const [key, name] of map)
        novels.normSeries.set(name, key);
    initSort(novels);
    initFilter(novels);
    initSearch(novels);
}

init().catch(error => {
    console.log(error);
    const s = `Error loading light novels: ${error}`;
    ROWS.prepend(getGroup(s, 'error'));
});
