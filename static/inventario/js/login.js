document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".login-password-toggle").forEach((passwordToggle) => {
        const passwordControl = passwordToggle.closest(".login-control");
        const passwordInput = passwordControl?.querySelector("input");

        if (!passwordInput) {
            return;
        }

        passwordToggle.addEventListener("click", () => {
            const passwordIsVisible = passwordInput.type === "text";

            passwordInput.type = passwordIsVisible ? "password" : "text";
            passwordToggle.setAttribute("aria-pressed", String(!passwordIsVisible));
            passwordToggle.setAttribute(
                "aria-label",
                passwordIsVisible ? "Mostrar senha" : "Ocultar senha",
            );
            passwordInput.focus();
        });
    });
});
