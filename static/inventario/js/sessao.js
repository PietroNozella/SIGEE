(() => {
    const statusUrl = document.currentScript.dataset.sessionStatusUrl;
    let timer;
    let consultando = false;

    // Reutilizado pelas consultas de disponibilidade e feriados.
    window.sigeeFetch = async (...args) => {
        const response = await fetch(...args);
        if (response.status === 401) {
            const payload = await response.clone().json();
            if (payload.codigo === "sessao_expirada") {
                window.location.replace(payload.login_url);
                throw new Error(payload.erro);
            }
        }
        return response;
    };

    const verificar = async () => {
        if (consultando) return;
        clearTimeout(timer);
        consultando = true;
        let intervalo = 30000;
        try {
            const response = await window.sigeeFetch(statusUrl, {
                headers: { Accept: "application/json" }, cache: "no-store",
            });
            if (response.ok) {
                const payload = await response.json();
                intervalo = Math.min(30000, Math.max(1000, payload.segundos_restantes * 1000));
            }
        } catch {
            // Falha de rede não significa logout; a próxima operação será validada no servidor.
        } finally {
            consultando = false;
            timer = setTimeout(verificar, intervalo);
        }
    };

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) verificar();
    });
    window.addEventListener("pageshow", verificar);
})();
