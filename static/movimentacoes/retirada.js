document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-withdrawal-form]");
    if (!form) return;
    const type = form.elements.tipo_equipamento;
    const location = form.elements.local;
    const quantity = form.elements.quantidade;
    const recipient = form.elements.destinatario;
    const body = form.querySelector("[data-withdrawal-equipment-list]");
    const status = form.querySelector("[data-withdrawal-status]");
    const availableLabel = form.querySelector("[data-withdrawal-available]");
    const quantityError = form.querySelector("[data-withdrawal-quantity-error]");
    const quantityDescription = quantity.getAttribute("aria-describedby");
    const quantityHasServerError = quantity.getAttribute("aria-invalid") === "true";
    const counter = form.querySelector("[data-withdrawal-selection-count]");
    const submit = form.querySelector("[data-withdrawal-submit]");
    const dialog = document.querySelector("[data-withdrawal-dialog]");
    const confirm = dialog.querySelector("[data-withdrawal-confirm-submit]");
    let availability = JSON.parse(document.querySelector("#withdrawal-initial-availability").textContent);
    let requestVersion = 0;
    let loading = false;
    let confirmed = false;
    let ajaxFailed = false;
    let controller;

    const selected = () => [...body.querySelectorAll("input[name=equipamentos]:checked")];
    const validQuantity = () => Number.isInteger(Number(quantity.value)) && Number(quantity.value) > 0;
    const updateSelection = () => {
        const count = selected().length;
        const desired = Number(quantity.value);
        const exceedsAvailability = Boolean(availability?.local) && desired > availability.equipamentos.length;
        const message = exceedsAvailability ? "Informe no máximo " + availability.equipamentos.length + " equipamentos." : "";
        quantityError.textContent = message;
        quantityError.hidden = !exceedsAvailability;
        quantity.setCustomValidity(message);
        quantity.classList.toggle("is-invalid", exceedsAvailability || quantityHasServerError);
        if (exceedsAvailability || quantityHasServerError) quantity.setAttribute("aria-invalid", "true");
        else quantity.removeAttribute("aria-invalid");
        const description = [quantityDescription, exceedsAvailability ? quantityError.id : ""].filter(Boolean).join(" ");
        if (description) quantity.setAttribute("aria-describedby", description);
        else quantity.removeAttribute("aria-describedby");
        counter.textContent = count + " de " + (validQuantity() ? desired : "—") + " equipamento(s) selecionado(s).";
        submit.disabled = loading || !availability?.local || !validQuantity() || exceedsAvailability || count !== desired;
    };
    const render = (ids) => {
        body.replaceChildren();
        const items = availability?.equipamentos || [];
        for (const item of items) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.name = "equipamentos";
            checkbox.value = String(item.id);
            checkbox.className = "form-check-input";
            checkbox.checked = ids.has(String(item.id));
            checkbox.setAttribute("aria-label", "Selecionar patrimônio " + item.patrimonio);
            cell.append(checkbox);
            row.append(cell);
            for (const value of [item.patrimonio, item.tipo, item.local]) {
                const textCell = document.createElement("td");
                textCell.textContent = value;
                row.append(textCell);
            }
            body.append(row);
        }
        if (!items.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 4;
            cell.textContent = availability?.local ? "Nenhum equipamento disponível neste local." : "Selecione o tipo/modelo e o local para consultar.";
            row.append(cell);
            body.append(row);
        }
        availableLabel.textContent = "(Disponível: " + (availability?.local ? items.length : "--") + ")";
        quantity.removeAttribute("max");
        if (availability?.local) quantity.max = String(items.length);
        updateSelection();
    };
    const suggest = () => {
        const count = validQuantity() ? Number(quantity.value) : 0;
        render(new Set((availability?.equipamentos || []).slice(0, count).map(item => String(item.id))));
        status.textContent = count > (availability?.equipamentos.length || 0)
            ? "A quantidade excede a disponibilidade. Reduza a quantidade para continuar."
            : "Confira os patrimônios sugeridos. Você pode trocar as unidades antes de confirmar.";
    };
    const consult = async () => {
        const version = ++requestVersion;
        controller?.abort();
        controller = new AbortController();
        const locationId = location.value;
        availability = null;
        loading = true;
        ajaxFailed = false;
        render(new Set());
        if (!type.value) {
            location.replaceChildren(new Option("Selecione um local", ""));
            loading = false;
            status.textContent = "Selecione o tipo/modelo e o local para consultar a disponibilidade.";
            updateSelection();
            return;
        }
        status.textContent = "Consultando equipamentos disponíveis…";
        const params = new URLSearchParams({tipo_equipamento: type.value});
        if (locationId) params.set("local", locationId);
        try {
            const response = await fetch(form.dataset.availabilityUrl + "?" + params, {
                signal: controller.signal, headers: {Accept: "application/json"},
            });
            const payload = await response.json();
            if (version !== requestVersion) return;
            if (!response.ok) throw new Error("Não foi possível consultar. Revise o tipo/modelo e o local.");
            availability = payload;
            location.replaceChildren(new Option("Selecione um local", ""));
            payload.locais.forEach(item => location.add(new Option(item.nome, String(item.id))));
            location.value = payload.local ? String(payload.local) : "";
            loading = false;
            if (!quantity.value) quantity.value = "1";
            suggest();
            if (!payload.local) status.textContent = "Selecione o local de retirada para consultar os equipamentos.";
        } catch (error) {
            if (version !== requestVersion || error.name === "AbortError") return;
            loading = false;
            ajaxFailed = true;
            render(new Set());
            status.textContent = "Não foi possível consultar a disponibilidade. Tente novamente ou use Consultar equipamentos.";
        }
    };
    type.addEventListener("change", () => {
        location.value = "";
        consult();
    });
    location.addEventListener("change", consult);
    quantity.addEventListener("input", suggest);
    body.addEventListener("change", updateSelection);
    form.querySelector("[data-withdrawal-consult]").addEventListener("click", event => {
        if (ajaxFailed) return;
        event.preventDefault();
        consult();
    });
    form.addEventListener("submit", event => {
        if (event.submitter?.value === "consultar") return;
        if (confirmed) {
            submit.disabled = true;
            confirm.disabled = true;
            return;
        }
        event.preventDefault();
        updateSelection();
        if (submit.disabled || !form.reportValidity()) return;
        if (typeof dialog.showModal !== "function") {
            confirmed = true;
            form.requestSubmit(submit);
            return;
        }
        dialog.querySelector("[data-withdrawal-confirm-recipient]").textContent = recipient.selectedOptions[0].textContent;
        dialog.querySelector("[data-withdrawal-confirm-scope]").textContent =
            type.selectedOptions[0].textContent + " — " + location.selectedOptions[0].textContent;
        dialog.querySelector("[data-withdrawal-confirm-quantity]").textContent = quantity.value;
        dialog.querySelector("[data-withdrawal-confirm-note]").textContent = form.elements.observacao.value.trim() || "Sem observação.";
        const ids = new Set(selected().map(item => item.value));
        const list = dialog.querySelector("[data-withdrawal-confirm-list]");
        list.replaceChildren();
        availability.equipamentos.filter(item => ids.has(String(item.id))).forEach(item => {
            const li = document.createElement("li");
            li.textContent = item.patrimonio;
            list.append(li);
        });
        dialog.showModal();
    });
    dialog.querySelector("[data-withdrawal-confirm-cancel]").addEventListener("click", () => dialog.close());
    confirm.addEventListener("click", () => {
        confirmed = true;
        dialog.close();
        form.requestSubmit(submit);
    });
    // Após erro do servidor, preservar os IDs conferidos que ainda estão disponíveis.
    const initialIds = new Set(selected().map(item => item.value));
    render(initialIds);
    if (availability?.local) {
        status.textContent = "Confira os patrimônios e a quantidade antes de confirmar.";
    }
});
