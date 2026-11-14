// static/products/js/comparison.js

document.addEventListener('DOMContentLoaded', function() {
    const comparisonCounts = document.querySelectorAll('#comparison-count, [data-comparison-count]');
    const emptyMessage = document.getElementById('empty-message');
    const tableWrapper = document.getElementById('comparison-table-wrapper');
    const table = document.getElementById('comparison-table');
    const scrollArea = table?.closest('.comparison-page__scroll');
    const scrollHint = document.getElementById('comparison-scroll-hint');
    let pendingRemoval = false;
    if (scrollArea && scrollHint) {
        const updateHint = () => { scrollHint.hidden = scrollArea.scrollWidth <= scrollArea.clientWidth; };
        new ResizeObserver(updateHint).observe(scrollArea);
        updateHint();
    }

    function updateComparisonUI(productId, isAdded, count, message) {
        // Обновляем счётчик в шапке
        comparisonCounts.forEach(counter => { counter.textContent = count; });

        // Обновляем кнопку на карточке
        document.querySelectorAll('.compare-btn[data-product-id="' + productId + '"]')
            .forEach(btn => {
                btn.classList.toggle('active', isAdded);
                const label = btn.querySelector('span');
                if (label) label.textContent = isAdded ? 'Убрать' : 'Сравнить';
            });

        if (table && !isAdded) {
            table.querySelectorAll('th, td').forEach(cell => {
                if (cell.dataset.productId === productId) cell.remove();
            });
            if (count === 0) {
                tableWrapper.style.display = 'none';
                emptyMessage.style.display = 'block';
                emptyMessage.querySelector('a').focus();
            } else {
                scrollHint.hidden = scrollArea.scrollWidth <= scrollArea.clientWidth;
                (table.querySelector('.remove-btn') || scrollArea).focus({preventScroll: true});
            }
        }

        // Показываем сообщение
        if (message) {
            showMessage(message);
        }
    }

    function showMessage(message) {
        const existing = document.querySelector('.comparison-message');
        if (existing) existing.remove();

        const div = document.createElement('div');
        div.className = 'comparison-message';
        div.style.cssText = 'position:fixed; bottom:20px; right:20px; background:#333; color:#fff; padding:12px 24px; border-radius:8px; z-index:999;';
        div.textContent = message;
        document.body.appendChild(div);

        setTimeout(() => div.remove(), 3000);
    }

    document.addEventListener('click', function(e) {
        const button = e.target.closest('.compare-btn[data-url]');
        if (!button || pendingRemoval || button.disabled || !button.dataset.url.startsWith('/catalog/comparison/toggle/')) return;
        e.preventDefault();
        button.disabled = true;
        pendingRemoval = Boolean(table);
        const url = button.dataset.url;
        const productId = button.dataset.productId;

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showMessage(data.message || 'Ошибка');
                return;
            }
            updateComparisonUI(productId, data.is_added, data.count, data.message);
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('Не удалось обновить сравнение. Попробуйте ещё раз.');
        })
        .finally(() => { button.disabled = false; pendingRemoval = false; });
    });
});
