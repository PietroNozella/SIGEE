document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-calendar-rule-form]");
    if (!form) return;
    const fields = form.querySelector("[data-time-fields]");
    const rows = form.querySelector("[data-time-rows]");
    const add = form.querySelector("[data-add-time]");
    const dateInput = form.querySelector("[data-calendar-date-input]");
    const dateToggle = form.querySelector("[data-reservation-calendar-toggle]");
    if (dateInput && dateToggle && !dateToggle.hidden) {
        document.querySelectorAll("#calendar-form-errors a").forEach(link => {
            if (link.getAttribute("href") === "#" + dateInput.id) link.setAttribute("href", "#" + dateToggle.id);
        });
    }
    const renumber = () => {
        let number = 0;
        rows.querySelectorAll("[data-time-row]").forEach(row => {
            if (row.hidden) return;
            number += 1;
            row.querySelector("[data-time-number]").textContent = String(number);
            row.querySelector("[data-remove-time]").setAttribute("aria-label", `Remover horário ${number}`);
        });
    };
    const prepareRow = row => {
        row.querySelector(".calendar-delete").hidden = true;
        row.querySelector("[data-remove-time]").hidden = false;
    };
    const initialRows = Array.from(rows.querySelectorAll("[data-time-row]"));
    const hasFilledRows = initialRows.some(row => Array.from(row.querySelectorAll("input[type='time']")).some(input => input.value));
    initialRows.forEach((row, index) => {
        prepareRow(row);
        const empty = Array.from(row.querySelectorAll("input[type='time']")).every(input => !input.value);
        const deleted = row.querySelector("input[type='checkbox']").checked;
        row.hidden = deleted || (empty && (hasFilledRows || index > 0) && !row.querySelector(".field-error"));
    });
    const update = () => {
        fields.hidden = form.querySelector("[name='funcionamento']:checked")?.value !== "FAIXAS";
    };
    form.querySelectorAll("[name='funcionamento']").forEach(input => input.addEventListener("change", update));
    update();
    add.hidden = false;
    add.addEventListener("click", () => {
        const total = form.querySelector("[name='faixas-TOTAL_FORMS']");
        const template = form.querySelector("[data-time-template]");
        const holder = document.createElement("div");
        holder.innerHTML = template.innerHTML.replaceAll("__prefix__", total.value);
        const row = holder.firstElementChild;
        rows.append(row);
        total.value = String(Number(total.value) + 1);
        prepareRow(row);
        renumber();
        row.querySelector("input[type='time']").focus();
    });
    rows.addEventListener("click", event => {
        const button = event.target.closest("[data-remove-time]");
        if (!button) return;
        const row = button.closest("[data-time-row]");
        row.querySelector("input[type='checkbox']").checked = true;
        row.hidden = true;
        renumber();
        const next = Array.from(rows.querySelectorAll("[data-time-row]")).find(item => !item.hidden);
        (next?.querySelector("input[type='time']") || add).focus();
    });
    renumber();
});
