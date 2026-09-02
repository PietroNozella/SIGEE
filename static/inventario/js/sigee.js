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

    const errorSummary = document.querySelector("[data-focus-on-load]");
    errorSummary?.focus();
});
