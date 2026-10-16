(() => {
    const categoryChart = document.getElementById('category-chart');
    const categoryOrder = document.getElementById('category-order');
    if (categoryChart && categoryOrder) {
        document.querySelector('[data-category-controls]').hidden = false;
        categoryOrder.addEventListener('change', () => {
            const rows = Array.from(categoryChart.children);
            rows.sort((a, b) => {
                const byName = a.dataset.name.localeCompare(b.dataset.name, 'pt-BR');
                if (categoryOrder.value === 'nome') return byName;
                if (categoryOrder.value === 'total') return Number(b.dataset.total) - Number(a.dataset.total) || byName;
                return Number(b.dataset.unavailable) - Number(a.dataset.unavailable)
                    || Number(b.dataset.total) - Number(a.dataset.total) || byName;
            });
            categoryChart.append(...rows);
        });
    }

    const days = Array.from(document.querySelectorAll('.timeline-day'));
    const detail = document.getElementById('day-detail');
    if (!days.length || !detail) return;
    document.querySelector('[data-day-feedback]').hidden = false;
    const inspect = index => {
        const day = days[index];
        days.forEach(other => {
            const selected = other === day;
            other.classList.toggle('is-selected', selected);
            other.setAttribute('aria-pressed', String(selected));
            other.tabIndex = selected ? 0 : -1;
        });
        const quantity = Number(day.dataset.count) === 1 ? 'unidade física retirada' : 'unidades físicas retiradas';
        detail.textContent = `${day.dataset.date} · ${day.dataset.count} ${quantity}`;
    };
    days.forEach((day, index) => {
        day.addEventListener('click', () => inspect(index));
        day.addEventListener('focus', () => inspect(index));
        day.addEventListener('pointerenter', event => {
            if (event.pointerType === 'mouse') inspect(index);
        });
        day.addEventListener('keydown', event => {
            let target;
            if (event.key === 'ArrowLeft') target = Math.max(0, index - 1);
            if (event.key === 'ArrowRight') target = Math.min(days.length - 1, index + 1);
            if (event.key === 'Home') target = 0;
            if (event.key === 'End') target = days.length - 1;
            if (target === undefined) return;
            event.preventDefault();
            days[target].focus();
        });
    });
    inspect(days.length - 1);
})();
