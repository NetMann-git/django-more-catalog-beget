// apps/products/static/products/js/wishlist.js
document.addEventListener('DOMContentLoaded', function() {
    const wishlistGrid = document.getElementById('wishlist-grid');
    const recommendedGrid = document.querySelector('.recommended-section .products-grid');
    const wishlistProducts = document.getElementById('wishlist-products');
    const emptyWishlist = document.getElementById('empty-wishlist');

    // Делегирование событий: ловим клики по кнопкам избранного и очистки
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.wishlist-btn');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            handleWishlistToggle(btn);
            return;
        }

        if (e.target.id === 'clear-wishlist' || e.target.closest('#clear-wishlist')) {
            e.preventDefault();
            e.stopPropagation();
            handleClearWishlist();
        }
    });

    function handleWishlistToggle(btn) {
        const url = btn.dataset.url;
        const card = btn.closest('.dress-card, .product-card, .housing-category__card');

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
            // Обновляем состояние кнопки
            const heart = btn.querySelector('.heart');
            const label = btn.querySelector('.label');

            if (data.is_favorite) {
                btn.classList.add('active');
                if (heart) heart.textContent = '❤️';
                if (label) label.textContent = 'В избранном';

                // Если мы на странице избранного и карточка находится в рекомендациях,
                // перемещаем её в список избранного (только визуальное перемещение)
                if (window.location.pathname.includes('/wishlist/') && card) {
                    if (recommendedGrid && recommendedGrid.contains(card)) {
                        wishlistGrid.prepend(card);
                        wishlistProducts.style.display = 'block';
                        emptyWishlist.style.display = 'none';
                    }
                }
            } else {
                btn.classList.remove('active');
                if (heart) heart.textContent = '🤍';
                if (label) label.textContent = 'В избранное';

                // Если на странице избранного и карточка в списке,
                // перемещаем её в рекомендации (или удаляем, если рекомендаций нет)
                if (window.location.pathname.includes('/wishlist/') && card) {
                    if (wishlistGrid && wishlistGrid.contains(card)) {
                        if (recommendedGrid) {
                            recommendedGrid.appendChild(card);
                        } else {
                            card.remove();
                        }

                        const remainingCards = wishlistGrid.querySelectorAll('.product-card, .dress-card, .housing-category__card').length;
                        if (remainingCards === 0) {
                            wishlistProducts.style.display = 'none';
                            emptyWishlist.style.display = 'block';
                        }
                    }
                }
            }

            document.querySelectorAll('#wishlist-count, [data-wishlist-count]')
                .forEach(counter => { counter.textContent = data.count; });
        })
        .catch(error => console.error('Ошибка переключения избранного:', error));
    }

    function handleClearWishlist() {
        const clearBtn = document.getElementById('clear-wishlist');
        const url = clearBtn.dataset.url;

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
                const grid = document.getElementById('wishlist-grid');
                if (grid) {
                    const cards = grid.querySelectorAll('.product-card, .dress-card, .housing-category__card');
                    cards.forEach(card => {
                        const btn = card.querySelector('.wishlist-btn');
                        if (btn) {
                            btn.classList.remove('active');
                            const heart = btn.querySelector('.heart');
                            const label = btn.querySelector('.label');
                            if (heart) heart.textContent = '🤍';
                            if (label) label.textContent = 'В избранное';
                        }

                        if (recommendedGrid) {
                            recommendedGrid.appendChild(card);
                        } else {
                            card.remove();
                        }
                    });
                }

                if (wishlistProducts) wishlistProducts.style.display = 'none';
                if (emptyWishlist) emptyWishlist.style.display = 'block';

                document.querySelectorAll('#wishlist-count, [data-wishlist-count]')
                    .forEach(counter => { counter.textContent = '0'; });
            }
        })
        .catch(error => console.error('Ошибка очистки избранного:', error));
    }
});
