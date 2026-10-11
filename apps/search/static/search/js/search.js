document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('search-input');
    const container = document.getElementById('search-results');
    if (!input || !container) return;
    let timer, revision = 0;
    const searchUrl = query => '/search/?query=' + encodeURIComponent(query);
    const hide = () => { container.style.display = 'none'; };
    function text(tag, value, className) {
        const node = document.createElement(tag);
        node.textContent = value || '';
        if (className) node.className = className;
        return node;
    }
    function title(value, query) {
        const node = text('div', '', 'search-item-title');
        const source = String(value || '');
        const start = source.toLocaleLowerCase('ru').indexOf(query.toLocaleLowerCase('ru'));
        if (!query || start < 0) node.textContent = source;
        else node.append(document.createTextNode(source.slice(0, start)),
            text('mark', source.slice(start, start + query.length)),
            document.createTextNode(source.slice(start + query.length)));
        return node;
    }
    function render(results, query, popular = false) {
        container.replaceChildren();
        if (!results.length) {
            if (popular) { hide(); return; }
            container.append(text('div', 'Ничего не найдено', 'search-empty'));
        } else {
            const list = text('ul', '', 'search-dropdown');
            results.forEach(result => {
                const item = text('li', '', 'search-item ' + (popular ? 'popular' : result.type));
                item.dataset.url = popular ? searchUrl(result) : result.url;
                if (!popular && result.image) {
                    const image = document.createElement('img');
                    image.src = result.image; image.alt = result.product_title || result.title;
                    image.loading = 'lazy';
                    const wrapper = text('div', '', 'search-item-image');
                    wrapper.append(image); item.append(wrapper);
                }
                const content = text('div', '', 'search-item-content');
                content.append(title(popular ? result : result.title, query));
                if (!popular) {
                    const meta = result.type === 'product' ? [result.brand, result.address].filter(Boolean).join(' · ')
                        : result.type === 'attribute' ? result.product_title : 'Категория жилья';
                    content.append(text('div', meta, 'search-item-meta'));
                }
                item.append(content); list.append(item);
            });
            container.append(list);
        }
        container.style.display = 'block';
    }
    input.addEventListener('focus', () => {
        if (input.value.trim()) return;
        const token = ++revision;
        fetch('/search/popular/').then(r => r.json()).then(data => {
            if (token === revision && !input.value.trim() && document.activeElement === input)
                render(data.popular || [], '', true);
        }).catch(hide);
    });
    input.addEventListener('input', () => {
        clearTimeout(timer);
        const query = input.value.trim(), token = ++revision;
        hide();
        if (query.length < 2) return;
        timer = setTimeout(() => {
            fetch('/search/suggest/?q=' + encodeURIComponent(query)).then(r => r.json()).then(data => {
                if (token === revision && document.activeElement === input) render(data.results || [], query);
            }).catch(hide);
        }, 250);
    });
    container.addEventListener('click', event => {
        const item = event.target.closest('.search-item');
        if (item && item.dataset.url) location.href = item.dataset.url;
    });
    document.addEventListener('click', event => {
        if (!event.target.closest('#search-container')) { ++revision; hide(); }
    });
    input.addEventListener('keydown', event => {
        if (event.key === 'Escape') { ++revision; hide(); return; }
        const items = container.style.display === 'none' ? [] : [...container.querySelectorAll('.search-item')];
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            if (!items.length) return;
            event.preventDefault();
            let index = items.findIndex(item => item.classList.contains('active'));
            index = event.key === 'ArrowDown' ? (index + 1) % items.length : (index <= 0 ? items.length : index) - 1;
            items.forEach(item => item.classList.remove('active'));
            items[index].classList.add('active'); items[index].scrollIntoView({block: 'nearest'});
        } else if (event.key === 'Enter') {
            event.preventDefault();
            const active = items.find(item => item.classList.contains('active'));
            if (active) location.href = active.dataset.url;
            else if (input.value.trim()) location.href = searchUrl(input.value.trim());
        }
    });
});
