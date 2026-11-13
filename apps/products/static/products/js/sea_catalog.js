const catalogFilters = document.querySelector('.sea-catalog__filters');
const narrowCatalog = window.matchMedia('(max-width: 760px)');

function updateCatalogFilters() {
    catalogFilters.open = !narrowCatalog.matches || Boolean(catalogFilters.querySelector('.errorlist'));
}

updateCatalogFilters();
narrowCatalog.addEventListener('change', updateCatalogFilters);
