(() => {
    const form = document.querySelector('[data-return-form]');
    if (!form) return;
    const units = [...form.querySelectorAll('input[name="retiradas"]')];
    const all = form.querySelector('[data-return-select-all]');
    const count = form.querySelector('[data-return-count]');
    const error = form.querySelector('[data-return-selection-error]');
    const dialog = document.querySelector('[data-return-dialog]');
    const submit = form.querySelector('[data-return-submit]');
    const confirm = dialog.querySelector('[data-return-confirm-submit]');
    let confirmed = false;
    const selected = () => units.filter(unit => unit.checked);
    function updateSelection() {
        const quantity = selected().length;
        all.checked = quantity === units.length && quantity > 0;
        all.indeterminate = quantity > 0 && quantity < units.length;
        count.textContent = `${quantity} de ${units.length} unidade(s) em aberto selecionada(s) para devolução.`;
        error.hidden = quantity > 0;
        confirmed = false;
    }
    form.querySelector('[data-return-select-all-label]').hidden = false;
    all.addEventListener('change', () => {
        units.forEach(unit => { unit.checked = all.checked; });
        updateSelection();
    });
    units.forEach(unit => unit.addEventListener('change', updateSelection));
    form.addEventListener('submit', event => {
        if (confirmed) {
            submit.disabled = true;
            return;
        }
        const received = selected();
        if (!received.length) {
            event.preventDefault();
            error.hidden = false;
            document.querySelector('#id_retiradas').focus();
            return;
        }
        if (typeof dialog.showModal !== 'function') return;
        event.preventDefault();
        dialog.querySelector('[data-return-confirm-count]').textContent = received.length;
        dialog.querySelector('[data-return-confirm-recipient]').textContent = document.querySelector('[data-return-recipient]').textContent;
        dialog.querySelector('[data-return-confirm-remaining]').textContent = `${units.length - received.length} unidade(s) continuarão pendentes de devolução.`;
        const list = dialog.querySelector('[data-return-confirm-list]');
        list.replaceChildren(...received.map(unit => {
            const item = document.createElement('li');
            item.textContent = unit.dataset.patrimonio;
            return item;
        }));
        confirm.disabled = false;
        dialog.showModal();
    });
    dialog.querySelector('[data-return-confirm-cancel]').addEventListener('click', () => dialog.close());
    confirm.addEventListener('click', () => {
        confirm.disabled = true;
        confirmed = true;
        dialog.close();
        form.requestSubmit();
    });
    updateSelection();
})();
