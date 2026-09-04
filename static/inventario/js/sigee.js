document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.querySelector("#app-sidebar");
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const closeControl = document.querySelector("[data-sidebar-close]");

    const setSidebarOpen = (open) => {
        if (!sidebar || !toggle) return;
        document.body.classList.toggle("sidebar-is-open", open);
        toggle.setAttribute("aria-expanded", String(open));
    };

    toggle?.addEventListener("click", () => {
        setSidebarOpen(!document.body.classList.contains("sidebar-is-open"));
    });
    closeControl?.addEventListener("click", () => setSidebarOpen(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setSidebarOpen(false);
    });

    const deleteDialog = document.querySelector("[data-delete-dialog]");
    const deleteName = document.querySelector("[data-delete-name]");
    const deletePatrimony = document.querySelector("[data-delete-patrimonio]");
    const deleteWarning = document.querySelector("[data-delete-warning]");
    const deleteConfirmLabel = document.querySelector("[data-delete-confirm-label]");
    const deleteConfirm = document.querySelector("[data-delete-confirm]");
    let deleteForm = null;
    let deleteTrigger = null;

    const closeDeleteDialog = () => {
        if (deleteDialog?.open) deleteDialog.close();
    };

    document.querySelectorAll("[data-delete-trigger]").forEach((trigger) => {
        trigger.addEventListener("click", () => {
            if (!deleteDialog || typeof deleteDialog.showModal !== "function") return;

            deleteForm = trigger.closest("form");
            deleteTrigger = trigger;

            if (!deleteForm) return;

            const possuiHistorico = trigger.dataset.possuiHistorico === "true";
            deleteName.textContent = trigger.dataset.equipamentoNome;
            deletePatrimony.textContent = trigger.dataset.equipamentoPatrimonio;
            deleteWarning.textContent = possuiHistorico
                ? "Este equipamento possui movimentações e será inativado. O histórico será preservado."
                : "Esta ação não poderá ser desfeita e removerá o item permanentemente do inventário.";
            deleteConfirmLabel.textContent = possuiHistorico
                ? "Sim, inativar equipamento"
                : "Sim, excluir equipamento";

            deleteDialog.showModal();
            deleteDialog.querySelector("[data-delete-close]")?.focus();
        });
    });

    deleteDialog?.querySelectorAll("[data-delete-close]").forEach((control) => {
        control.addEventListener("click", closeDeleteDialog);
    });

    deleteDialog?.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeDeleteDialog();
    });

    deleteDialog?.addEventListener("click", (event) => {
        if (event.target === deleteDialog) closeDeleteDialog();
    });

    deleteDialog?.addEventListener("close", () => {
        deleteTrigger?.focus();
        deleteForm = null;
        deleteTrigger = null;
    });

    deleteConfirm?.addEventListener("click", () => {
        const form = deleteForm;

        if (!form) return;

        closeDeleteDialog();
        form.requestSubmit();
    });

    const errorSummary = document.querySelector("[data-focus-on-load]");
    errorSummary?.focus();
});
