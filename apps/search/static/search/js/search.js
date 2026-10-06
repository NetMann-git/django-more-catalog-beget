// apps/search/static/search/js/search.js
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-input');
    const resultsContainer = document.getElementById('search-results');

    if (!searchInput) return;

    const priceFormatter = new Intl.NumberFormat('ru-RU', {maximumFractionDigits: 2});
    const formatPrice = value => {
        const number = Number(value);
        return Number.isFinite(number) ? priceFormatter.format(number) : '';
    };

    let debounceTimer;

    // Показываем популярные запросы при фокусе (если поле пустое)
    searchInput.addEventListener('focus', function() {
        const query = this.value.trim();
        if (query.length === 0 && resultsContainer.children.length === 0) {
            fetch('/search/popular/')
                .then(response => response.json())
                .then(data => {
                    renderPopular(data.popular);
                })
                .catch(error => console.error('Ошибка загрузки популярных запросов:', error));
        }
    });

    // Поиск по вводу (с debounce)
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();

        if (query.length < 2) {
            resultsContainer.style.display = 'none';
            return;
        }

        debounceTimer = setTimeout(() => {
            fetch(`/search/suggest/?q=${encodeURIComponent(query)}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                renderResults(data.results, query);
            })
            .catch(error => console.error('Ошибка поиска:', error));
        }, 250);
    });

    function renderResults(results, query) {
        if (!results || results.length === 0) {
            resultsContainer.innerHTML = '<div class="search-empty">Ничего не найдено</div>';
            resultsContainer.style.display = 'block';
            return;
        }

        let html = '<ul class="search-dropdown">';
        results.forEach(item => {
            if (item.type === 'product') {
                html += `
                    <li class="search-item product" data-url="${item.url}">
                        <div class="search-item-image">
                            ${item.image ? `<img src="${item.image}" alt="${item.title}">` : ''}
                        </div>
                        <div class="search-item-content">
                            <div class="search-item-title">${highlightText(item.title, query)}</div>
                            <div class="search-item-meta">
                                ${item.price !== null && item.price !== undefined && item.price !== '' ? `<span class="price">${formatPrice(item.price)} ${item.currency}</span>` : '<span class="price">Цена по запросу</span>'}
                                ${item.category ? `<span class="category">${item.category}</span>` : ''}
                            </div>
                            ${item.badges && item.badges.length ? `<div class="search-item-badges">${item.badges.map(b => `<span class="badge badge-${b.slug}">${b.title}</span>`).join('')}</div>` : ''}
                        </div>
                    </li>
                `;
            } else if (item.type === 'attribute') {
                html += `
                    <li class="search-item attribute" data-url="${item.url}">
                        <div class="search-item-image">
                            ${item.image ? `<img src="${item.image}" alt="${item.product_title}">` : ''}
                        </div>
                        <div class="search-item-content">
                            <div class="search-item-title">${highlightText(item.title, query)}</div>
                            <div class="search-item-meta">
                                ${item.price !== null && item.price !== undefined && item.price !== '' ? `<span class="price">${formatPrice(item.price)} ${item.currency}</span>` : '<span class="price">Цена по запросу</span>'}
                                <span class="search-item-type">Характеристика</span>
                            </div>
                        </div>
                    </li>
                `;
            } else {
                html += `
                    <li class="search-item category" data-url="${item.url}">
                        <span class="search-item-title">${highlightText(item.title, query)}</span>
                        <span class="search-item-type">${item.type === 'category' ? 'Категория' : 'Бейдж'}</span>
                    </li>
                `;
            }
        });
        html += '</ul>';
        resultsContainer.innerHTML = html;
        resultsContainer.style.display = 'block';
    }

    function renderPopular(queries) {
        if (!queries || queries.length === 0) {
            resultsContainer.style.display = 'none';
            return;
        }
        let html = '<ul class="search-dropdown popular">';
        queries.forEach(q => {
            html += `<li class="search-item popular" data-query="${q}">🔍 ${q}</li>`;
        });
        html += '</ul>';
        resultsContainer.innerHTML = html;
        resultsContainer.style.display = 'block';
    }

    // Подсветка совпадений
    function highlightText(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    // Клик по результату – переход по ссылке
    document.addEventListener('click', function(e) {
        const item = e.target.closest('.search-item');
        if (item) {
            if (item.classList.contains('popular')) {
                const query = item.dataset.query;
                window.location.href = `/catalog/?q=${encodeURIComponent(query)}`;
                return;
            }
            if (item.dataset.url) {
                window.location.href = item.dataset.url;
            }
        } else if (!e.target.closest('#search-container')) {
            resultsContainer.style.display = 'none';
        }
    });

    // Клавиатура (↓ ↑ Enter Esc)
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            resultsContainer.style.display = 'none';
            searchInput.blur();
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const items = resultsContainer.querySelectorAll('.search-item');
            if (!items.length) return;
            let currentIndex = Array.from(items).findIndex(el => el.classList.contains('active'));
            if (e.key === 'ArrowDown') {
                if (currentIndex < items.length - 1) currentIndex++;
                else currentIndex = 0;
            } else {
                if (currentIndex > 0) currentIndex--;
                else currentIndex = items.length - 1;
            }
            items.forEach(el => el.classList.remove('active'));
            items[currentIndex].classList.add('active');
            items[currentIndex].scrollIntoView({ block: 'nearest' });
        }
        if (e.key === 'Enter') {
            const active = resultsContainer.querySelector('.search-item.active');
            if (active) {
                if (active.classList.contains('popular')) {
                    const query = active.dataset.query;
                    window.location.href = `/catalog/?q=${encodeURIComponent(query)}`;
                } else if (active.dataset.url) {
                    window.location.href = active.dataset.url;
                }
            }
        }
    });
});