document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-calendar-rule-form]");
    if (!form) return;
    const fields = form.querySelector("[data-time-fields]");
    const update = () => { fields.hidden = form.querySelector("[name='funcionamento']:checked")?.value !== "FAIXAS"; };
    form.querySelectorAll("[name='funcionamento']").forEach(input => input.addEventListener("change", update));
    update();
    const add = form.querySelector("[data-add-time]");
    add.hidden = false;
    add.addEventListener("click", () => {
        const total = form.querySelector("[name='faixas-TOTAL_FORMS']");
        const template = form.querySelector("[data-time-template]");
        const row = document.createElement("div");
        row.innerHTML = template.innerHTML.replaceAll("__prefix__", total.value);
        form.querySelector("[data-time-rows]").append(...row.childNodes);
        total.value = String(Number(total.value) + 1);
        form.querySelector("[data-time-rows]").lastElementChild.querySelector("input[type='time']")?.focus();
    });
});
