document.addEventListener("DOMContentLoaded", () => {
    const passwordInput = document.querySelector(".login-control input[type='password']");
    const passwordToggle = document.querySelector(".login-password-toggle");

    if (!passwordInput || !passwordToggle) {
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
