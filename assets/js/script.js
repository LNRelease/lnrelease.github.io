const COLUMNS = 5;
const CHUNK_SIZE = 256;
const GROUP_THRESHOLD = 40;
const YEAR_THRESHOLD = 24;
const SEARCH_THRESHOLD = 800;

const PHYSICAL = 1;
const DIGITAL = 2;
const PHYSICAL_DIGITAL = 3;
const AUDIOBOOK = 4;

const BODY = document.body;
const TABLE = document.getElementById('table');
const TBODY = TABLE.querySelector('tbody');
const SHOWN = document.getElementById('shown');
const SEARCH = document.getElementById('search');
const HEADERS = TABLE.querySelectorAll('.sort');
const LOADING = document.getElementById('loading');
const STAR = document.getElementById('star');
const SERIES = document.getElementById('menu-title');

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

// Scroll when novels loaded
let hashFragment = window.location.hash.substring(1) || null;

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
settings.star ??= false;
settings.series ??= [];
settings.publisher ??= [];
settings.format ??= [PHYSICAL, DIGITAL, PHYSICAL_DIGITAL];
storage?.setItem('settings', JSON.stringify(settings));

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


class Novels extends Array {
    constructor({ data, series, publishers }) {
        super();
        this.filters = {
            date: dateFilter(),
            star: new Set(settings.series),
            volume: { start: '', end: '' },
            publisher: new Set(publishers.filter(item =>
                !settings.publisher.includes(item))),
            format: new Set(settings.format),
        };

        const groupFormat = new Intl.DateTimeFormat(undefined, {
            year: 'numeric',
            month: 'long',
        });
        this.shown = 0;
        for (const item of data) {
            const book = new Book(item, series, publishers, groupFormat, this.filters);
            this.push(book);
            if (book.filter) {
                this.shown++;
                book.show = true;
            }
        }
        this.order = 0;
        this.grouped = this.order % COLUMNS === 0;
        this.updater = undefined;
        this.publishers = publishers;
        this.series = new Map(series);
        this.stars = new Map();
        rebuildTable(this, this.grouped);
        document.getElementById('total').textContent = this.length;
    }

    static get [Symbol.species]() { return Array; }
}

class Book {
    constructor(item, series, publishers, groupFormat, filters) {
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
        this.group = groupFormat.format(date);
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
        this.normSeries = undefined;
        this.normTitle = undefined;
        this.search = undefined;
    }

    norm() { // Takes a little time
        this.normSeries = norm(this.series);
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
                format = 'audiobook'
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

function createRow(book) {
    if (book.row)
        return book.row;

    book.row = document.createElement('tr');

    const cell0 = book.row.insertCell(0);
    cell0.textContent = book.date;

    const cell1 = book.row.insertCell(1);
    cell1.title = book.publisher;
    const a = document.createElement('a');
    a.href = book.link;
    a.textContent = book.title;
    const span = document.createElement('span');
    span.textContent = '⭐';
    span.title = '';
    span.dataset.series = book.serieskey;
    span.classList.add('star');
    if (book.filters.star)
        span.classList.add('star-active');
    cell1.append(a, span);

    const cell2 = book.row.insertCell(2);
    cell2.textContent = book.volume;

    const cell3 = book.row.insertCell(3);
    cell3.textContent = book.publisher;

    const cell4 = book.row.insertCell(4);
    cell4.title = book.isbn;
    switch (book.format) {
        case PHYSICAL: {
            const span = document.createElement('span');
            span.className = 'hidden';
            span.textContent = '🖥️';
            cell4.append(span, '📖');
            break;
        } case DIGITAL: {
            const span = document.createElement('span');
            span.className = 'hidden';
            span.textContent = '📖';
            cell4.append('🖥️', span);
            break;
        } case PHYSICAL_DIGITAL: {
            cell4.textContent = '🖥️📖';
            break;
        } case AUDIOBOOK: {
            cell4.textContent = '🔊';
            break;
        }
    }
    return book.row;
}

function createGroup(month, id) {
    const row = document.createElement('tr');
    const cell = document.createElement('th');
    cell.textContent = month;
    cell.colSpan = COLUMNS;
    cell.id = id;
    row.appendChild(cell);
    return row;
}

function checkGroups(rows, groups, count, year) {
    if (count <= YEAR_THRESHOLD && groups.length) {
        for (const [i, group] of groups.entries()) {
            i ? rows.delete(group)
                : rows.get(group).firstElementChild.textContent = year;
        }
    }
}

async function redrawTable(novels, rows) {
    const updater = {};
    novels.updater = updater;
    SHOWN.textContent = novels.shown;
    const children = [];
    let i = 0;
    BODY.style.minHeight = BODY.scrollHeight + 'px';
    LOADING.style.display = 'block';
    for (const row of rows.values()) {
        i++;
        children.push(row instanceof Book ? createRow(row) : row);
        if (i % CHUNK_SIZE === 0) {
            i === CHUNK_SIZE ? TBODY.replaceChildren(...children)
                : TBODY.append(...children);
            children.length = 0;
            TBODY.offsetWidth; // Force reflow
            await new Promise(resolve => setTimeout(resolve));
            if (novels.updater !== updater)
                return;
        }
    }
    i < CHUNK_SIZE ? TBODY.replaceChildren(...children)
        : TBODY.append(...children);
    BODY.style.minHeight = null;
    LOADING.style.display = null;
    if (hashFragment) {
        document.getElementById(hashFragment)?.scrollIntoView();
        hashFragment = null;
    }
}

function rebuildTable(novels, group = null) {
    let i = 0;
    let groupStart, groupName, groups, year;
    const rows = new Map();
    group ??= novels.grouped;
    novels.grouped = group;
    group &= novels.shown > GROUP_THRESHOLD;

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
            rows.set(i++, createGroup(book.group, book.id));
        }
        rows.set(i++, book);
    }
    checkGroups(rows, groups, i - groupStart, year);
    redrawTable(novels, rows);
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
    novels.shown = 0;
    if (search) {
        const include = [];
        const exclude = [];
        for (const word of search.matchAll(/(?<!\S)(?:-?".+"|\S+)(?!\S)/g)) {
            const normWord = norm(word[0]);
            if (normWord)
                (word[0][0] === '-' ? exclude : include).push(normWord);
        }
        for (const book of novels) {
            book.show = searchBook(book, include, exclude);
            if (book.show) novels.shown++;
        }
        if (novels.shown > SEARCH_THRESHOLD) {
            for (const book of novels) {
                if (book.show && !book.filter) {
                    book.show = false;
                    novels.shown--;
                }
            }
        }
    } else {
        for (const book of novels) {
            book.show = book.filter;
            if (book.show) novels.shown++;
        }
    }
    rebuildTable(novels);
}

function sortTable(novels, index) {
    const group = index === 0;
    HEADERS[novels.order % COLUMNS].classList.remove('sort-desc', 'sort-asc');
    const newClasses = HEADERS[index].classList;
    if (novels.order === index) {
        newClasses.remove('sort-desc');
        newClasses.add('sort-asc');
        index += COLUMNS;
    } else {
        newClasses.remove('sort-asc');
        newClasses.add('sort-desc');
    }
    novels.order = index;

    novels.sort(COMPARATORS[index]);
    rebuildTable(novels, group);
}

function initSort(novels) {
    for (const [i, th] of HEADERS.entries()) {
        th.addEventListener('click', e => {
            if (e.target === th)
                sortTable(novels, i);
        });
    }
}

function createStar(novels, serieskey, series) {
    const div = document.createElement('div');
    div.classList.add('list-row');
    const text = document.createElement('span');
    text.textContent = series;
    text.classList.add('row-text');
    const btn = document.createElement('span');
    btn.textContent = '⨉';
    btn.classList.add('menu-btn');
    btn.addEventListener('click', e => {
        e.stopPropagation();
        unstarSeries(novels, serieskey, div);
    });
    div.append(text, btn);
    let next;
    for (const [key, value] of novels.stars.entries()) {
        if (serieskey < key) {
            next = value;
            break;
        }
    }
    next ? SERIES.insertBefore(div, next) : SERIES.appendChild(div);
    novels.stars.set(serieskey, div);
}

function starSeries(novels, serieskey, series) {
    novels.filters.star.add(serieskey);
    for (const book of novels) {
        if (book.serieskey === serieskey) {
            book.filters.star = true;
            if (settings.star) book.filter = book.getFilter();
            book.row?.querySelector('.star').classList.add('star-active');
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
            book.row?.querySelector('.star').classList.remove('star-active');
        }
    }
    if (settings.star) filterTable(novels);
    div.remove();
}

function initDate(novels) {
    const th = HEADERS[0].classList;
    const start = document.getElementById('date-start');
    const end = document.getElementById('date-end');
    const dates = novels.filters.date;
    if (dates.start) {
        start.value = new Date(dates.start)
            .toISOString().substring(0, 10);
        th.add('filter');
    }
    if (dates.end) {
        end.value = new Date(dates.end)
            .toISOString().substring(0, 10);
        th.add('filter');
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
            th.add('filter');
        });

    function filter(event) {
        const filter = novels.filters.date;
        const target = event.target;
        filter[target.name] = new Date(target.value).getTime() || null;
        for (const book of novels)
            book.filterDate(filter);
        filterTable(novels);
        filter.start || filter.end ? th.add('filter') : th.remove('filter');
    }

    start.addEventListener('input', filter);
    end.addEventListener('input', filter);
}

function initTitle(novels) {
    const th = HEADERS[1].classList;
    document.getElementById('series')
        .append(...Array.prototype.map.call(novels.series.values(),
            series => {
                const option = document.createElement('option');
                option.value = series;
                return option;
            }));
    const search = document.getElementById('filter-search');
    const add = document.getElementById('star-add');
    if (search.value || settings.star) th.add('filter');

    const series = new Map(novels.map(book => [book.normSeries, book.serieskey]));
    search.addEventListener('input', () => {
        const value = search.value;
        const normValue = norm(value);
        const key = series.get(normValue);
        if (key) {
            add.classList.remove('disabled');
            for (const book of novels) {
                const old = book.filters.title;
                book.filters.title = key === book.serieskey;
                if (old !== book.filters.title)
                    book.filter = !old && book.getFilter();
            }
        } else {
            add.classList.add('disabled');
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
        value ? th.add('filter') : th.remove('filter');
    });
    add.addEventListener('click', () => {
        const key = series.get(norm(search.value));
        if (key) starSeries(novels, key, novels.series.get(key));
    });

    STAR.checked = settings.star;
    STAR.addEventListener('change', () => {
        settings.star = STAR.checked;
        for (const book of novels)
            book.filter = !settings.star ? book.getFilter()
                : book.filter && book.filters.star;
        filterTable(novels);
        settings.star ? th.add('filter') : th.remove('filter');
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
                    book.row?.querySelector('.star')
                        .classList.remove('star-active');
                }
            }
            filterTable(novels);
            th.remove('filter');
            for (const row of novels.stars.values())
                row.remove();
            novels.filters.star.clear();
            novels.stars.clear();
        });
}

function initVolume(novels) {
    const th = HEADERS[2].classList;
    const start = document.getElementById('vol-start');
    const end = document.getElementById('vol-end');
    if (start.value || end.value) th.add('filter');
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
            th.remove('filter');
        });
    function filter(event) {
        const filter = novels.filters.volume;
        const target = event.target;
        filter[target.name] = target.value.trim();
        for (const book of novels)
            book.filterVolume(filter);
        filterTable(novels);
        filter.start || filter.end ? th.add('filter') : th.remove('filter');
    }
    start.addEventListener('input', filter);
    end.addEventListener('input', filter);
}

function initPublisher(novels) {
    const th = HEADERS[3].classList;
    const select = document.getElementById('pub-select')
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
        menu.appendChild(label);
        checkbox.addEventListener('change', e => {
            select.textContent = boxes.every(box => !box.checked) ? '☐' : '🗹';
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
            boxes.some(box => !box.checked) ? th.add('filter')
                : th.remove('filter');
        });
        return checkbox;
    });

    if (filter) th.add('filter');
    select.textContent = checked ? '🗹' : '☐';
    document.getElementById('pub-select')
        .addEventListener('click', () => {
            const b = select.textContent === '☐'
            select.textContent = b ? '🗹' : '☐';
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
            b ? th.remove('filter') : th.add('filter');
        });
    document.getElementById('pub-reset')
        .addEventListener('click', () => {
            for (const box of boxes)
                box.checked = true;
            select.textContent = '🗹';
            novels.filters.publisher = new Set(novels.publishers);
            for (const book of novels) {
                if (!book.filters.publisher) {
                    book.filters.publisher = true;
                    book.filter = book.getFilter();
                }
            }
            filterTable(novels);
            th.remove('filter');
        });
}

function initFormat(novels) {
    const th = HEADERS[4].classList;
    const menu = document.getElementById('menu-format');
    const select = document.getElementById('format-select');

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
                select.textContent = boxes.every(box => !box[0].checked) ? '☐' : '🗹';
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
                boxes.some(box => !box[0].checked) ? th.add('filter')
                    : th.remove('filter');
            });
            return [box, format];
        });

    if (filter) th.add('filter');
    select.textContent = checked ? '🗹' : '☐';
    document.getElementById('format-select')
        .addEventListener('click', () => {
            const b = select.textContent === '☐'
            select.textContent = b ? '🗹' : '☐';
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
            b ? th.remove('filter') : th.add('filter');
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
            select.textContent = tick ? '🗹' : '☐';
            for (const book of novels)
                book.filterFormat(filter);
            filterTable(novels);
            boxes.some(box => !box[0].checked) ? th.add('filter')
                : th.remove('filter');
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
        const classes = target.classList;
        if (!classes.contains('star'))
            return;

        const serieskey = target.dataset.series;
        classes.contains('star-active') ?
            unstarSeries(novels, serieskey, novels.stars.get(serieskey))
            : starSeries(novels, serieskey, novels.series.get(serieskey));
    }

    TBODY.addEventListener('click', e => toggleStar(e.target));
    TBODY.addEventListener('contextmenu', e => {
        const target = e.target.querySelector('.star') || e.target;
        toggleStar(target);
        e.preventDefault();
    });
    if (storage) { // Save on exit
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                Object.keys(settings).forEach(key => delete settings[key]);
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

fetch('data.json')
    .then(response => response.json())
    .then(data => {
        const novels = new Novels(data);
        return new Promise(resolve => setTimeout(() => resolve(novels)));
    })
    .then(novels => {
        for (const book of novels) book.norm();
        initSort(novels);
        initFilter(novels);
        initSearch(novels);
    })
    .catch(error => {
        console.log(error);
        const row = TBODY.insertRow();
        const cell = row.insertCell();
        cell.textContent = `Error loading light novels: ${error}`;
        cell.colSpan = COLUMNS;
    });
