// apps/products/static/products/js/recently_viewed.js
document.addEventListener('DOMContentLoaded', function() {

    // 1. Очистка на странице товара (кнопка #clear-recently-viewed)
    const clearBtnProduct = document.getElementById('clear-recently-viewed');
    if (clearBtnProduct) {
        clearBtnProduct.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.dataset.url;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Скрываем блок на странице товара
                    const grid = document.getElementById('recently-viewed-grid');
                    if (grid) grid.style.display = 'none';
                    const section = clearBtnProduct.closest('.recently-viewed');
                    if (section) section.style.display = 'none';
                    // Обновляем счётчик
                    document.querySelectorAll('#recently-viewed-count, [data-recently-viewed-count]')
                        .forEach(counter => { counter.textContent = '0'; });
                }
            })
            .catch(error => console.error('Ошибка:', error));
        });
    }

    // 2. Очистка на странице истории (кнопка #clear-recently-viewed-history)
    const clearBtnHistory = document.getElementById('clear-recently-viewed-history');
    if (clearBtnHistory) {
        clearBtnHistory.addEventListener('click', function(e) {
            e.preventDefault();
            if (clearBtnHistory.disabled) return;
            clearBtnHistory.disabled = true;
            const status = document.getElementById('history-clear-status');
            if (status) status.textContent = '';
            const url = this.dataset.url;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            })
            .then(response => {
                if (!response.ok) throw new Error(response.statusText);
                return response.json();
            })
            .then(data => {
                if (!data.success) throw new Error("History was not cleared");
                // Скрываем блок с товарами, показываем блок с сообщением
                const productsBlock = document.getElementById('recently-viewed-products');
                const emptyBlock = document.getElementById('empty-history-message');
                if (productsBlock) productsBlock.style.display = 'none';
                if (emptyBlock) {
                    emptyBlock.style.display = 'block';
                    emptyBlock.querySelector('a')?.focus();
                }
                // Обновляем счётчик
                document.querySelectorAll('#recently-viewed-count, [data-recently-viewed-count]')
                    .forEach(counter => { counter.textContent = '0'; });
            })
            .catch(error => {
                console.error('Ошибка:', error);
                if (status) status.textContent = 'Не удалось очистить историю. Попробуйте ещё раз.';
            })
            .finally(() => { clearBtnHistory.disabled = false; });
        });
    }

});
