/* Typed attribute controls shared by manager forms and Django admin inlines. */
(() => {
    'use strict';
    const initialized = new WeakSet();
    function initialize(root) {
        root.querySelectorAll('[data-attribute-type]').forEach((type) => {
            if (initialized.has(type) || type.closest('.empty-form')) return;
            const row = type.closest('[data-product-attribute-row], tr');
            if (!row) return;
            const choice = row.querySelector('[data-attribute-choice]');
            const input = row.querySelector('[data-attribute-input]');
            if (!choice || !input) return;
            initialized.add(type);
            const options = Array.from(choice.options, option => option.cloneNode(true));
            // Иконки выбранного типа и значения в обоих редакторах.
            function addPreview(select) {
                const image = document.createElement('img');
                image.width = 24;
                image.height = 24;
                image.alt = '';
                image.style.objectFit = 'contain';
                select.after(image);
                return image;
            }
            const typeIcon = addPreview(type);
            const valueIcon = addPreview(choice);
            function updateIcons() {
                [[type, typeIcon], [choice, valueIcon]].forEach(([select, image]) => {
                    const url = select.selectedOptions[0]?.dataset.icon;
                    image.hidden = !url || select.disabled;
                    if (url) image.src = url;
                    else image.removeAttribute('src');
                });
            }
            choice.addEventListener('change', updateIcons);
            function update() {
                const option = type.selectedOptions[0];
                const kind = option ? option.dataset.kind : '';
                const isChoice = kind === 'choice';
                const selected = choice.value;
                choice.replaceChildren(...options.filter(item =>
                    !item.value || item.dataset.owner === type.value
                ).map(item => item.cloneNode(true)));
                choice.value = selected;
                choice.disabled = !isChoice;
                choice.required = isChoice;
                input.disabled = !kind || isChoice;
                input.required = !!kind && !isChoice;
                input.type = kind === 'number' ? 'number' : 'text';
                input.removeAttribute('min');
                input.removeAttribute('step');
                if (kind === 'number') {
                    const mileage = option.dataset.slug === 'mileage';
                    input.step = mileage ? '1' : 'any';
                    if (mileage) input.min = '0';
                }
                updateIcons();
                const choiceContainer = row.querySelector('[data-attribute-choice-container]');
                const inputContainer = row.querySelector('[data-attribute-input-container]');
                (choiceContainer || choice).hidden = !isChoice;
                (inputContainer || input).hidden = !kind || isChoice;
            }
            type.addEventListener('change', update);
            update();
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initialize(document));
    } else {
        initialize(document);
    }
    document.addEventListener('formset:added', event => initialize(event.target));
})();
