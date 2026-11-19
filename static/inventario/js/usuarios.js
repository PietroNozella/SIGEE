(() => {
    const lista = document.querySelector('[data-user-emails]');
    if (!lista) return;

    const botoes = [...lista.querySelectorAll('[data-email-reveal]')];
    const status = lista.querySelector('[data-email-status]');
    const token = lista.querySelector('[name="csrfmiddlewaretoken"]').value;
    let visivel = null;
    let consulta = null;

    const ocultar = () => {
        if (!visivel) return;
        visivel.parentElement.querySelector('[data-email-value]').textContent = 'E-mail oculto';
        visivel.setAttribute('aria-pressed', 'false');
        visivel.setAttribute('aria-label', visivel.getAttribute('aria-label').replace(/^Ocultar/, 'Revelar'));
        visivel = null;
    };

    const limpar = () => {
        ocultar();
        consulta?.abort();
        consulta = null;
        botoes.forEach(botao => { botao.disabled = false; });
        status.textContent = '';
    };

    botoes.forEach(botao => {
        botao.addEventListener('click', async () => {
            if (consulta) return;
            const estavaVisivel = visivel === botao;
            ocultar();
            status.textContent = '';
            if (estavaVisivel) return;

            const requisicao = new AbortController();
            consulta = requisicao;
            botoes.forEach(item => { item.disabled = true; });
            status.textContent = 'Consultando e-mail…';
            try {
                const resposta = await window.sigeeFetch(botao.dataset.emailReveal, {
                    method: 'POST', mode: 'same-origin', cache: 'no-store',
                    headers: { Accept: 'application/json', 'X-CSRFToken': token },
                    signal: requisicao.signal,
                });
                if (!resposta.ok || resposta.redirected) throw new Error('Acesso não concluído');
                const dados = await resposta.json();
                if (consulta !== requisicao) return;
                if (typeof dados.email !== 'string') throw new Error('Resposta inválida');
                botao.parentElement.querySelector('[data-email-value]').textContent = dados.email;
                botao.setAttribute('aria-pressed', 'true');
                botao.setAttribute('aria-label', botao.getAttribute('aria-label').replace(/^Revelar/, 'Ocultar'));
                visivel = botao;
                status.textContent = 'Acesso ao e-mail registrado na auditoria.';
            } catch {
                if (consulta === requisicao) {
                    status.textContent = 'Não foi possível revelar o e-mail. Atualize a página ou tente novamente.';
                }
            } finally {
                if (consulta === requisicao) {
                    consulta = null;
                    botoes.forEach(item => { item.disabled = false; });
                }
            }
        });
    });

    window.addEventListener('pagehide', limpar);
    window.addEventListener('pageshow', limpar);
})();
