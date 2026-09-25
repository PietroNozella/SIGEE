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

    const userMenu = document.querySelector(".user-menu");
    document.addEventListener("click", (event) => {
        if (userMenu?.open && !userMenu.contains(event.target)) {
            userMenu.open = false;
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && userMenu?.open) {
            userMenu.open = false;
            userMenu.querySelector("summary")?.focus();
        }
    });

    const logoutForm = document.querySelector(".logout-form");
    const logoutTrigger = logoutForm?.querySelector("[data-logout-trigger]");
    const logoutDialog = document.querySelector("[data-logout-dialog]");
    const logoutConfirm = logoutDialog?.querySelector("[data-logout-confirm]");
    const logoutCancel = logoutDialog?.querySelector("[data-logout-cancel]");
    const logoutClose = logoutDialog?.querySelector("[data-logout-close]");
    let logoutConfirmed = false;

    const closeLogoutDialog = () => {
        if (logoutDialog?.open) logoutDialog.close();
    };

    logoutForm?.addEventListener("submit", (event) => {
        if (logoutConfirmed) {
            logoutConfirmed = false;
            return;
        }

        if (logoutDialog && typeof logoutDialog.showModal === "function") {
            event.preventDefault();
            logoutDialog.showModal();
            logoutConfirm?.focus();
        }
    });

    logoutConfirm?.addEventListener("click", () => {
        if (!logoutForm) return;
        logoutConfirmed = true;
        closeLogoutDialog();
        logoutForm.requestSubmit(logoutTrigger);
    });

    [logoutCancel, logoutClose].forEach((control) => {
        control?.addEventListener("click", closeLogoutDialog);
    });

    logoutDialog?.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeLogoutDialog();
    });

    logoutDialog?.addEventListener("click", (event) => {
        if (event.target === logoutDialog) closeLogoutDialog();
    });

    logoutDialog?.addEventListener("close", () => {
        if (!logoutConfirmed) logoutTrigger?.focus();
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

    const cancelReservationDialog = document.querySelector("[data-cancel-reservation-dialog]");
    const cancelReservationForm = document.querySelector("[data-cancel-reservation-form]");
    const cancelReservationEquipment = document.querySelector("[data-cancel-reservation-equipment]");
    const cancelReservationDate = document.querySelector("[data-cancel-reservation-date]");
    let cancelReservationTrigger = null;

    const closeCancelReservationDialog = () => {
        if (cancelReservationDialog?.open) cancelReservationDialog.close();
    };

    document.querySelectorAll("[data-cancel-reservation-trigger]").forEach((trigger) => {
        trigger.addEventListener("click", () => {
            if (
                !cancelReservationDialog
                || !cancelReservationForm
                || typeof cancelReservationDialog.showModal !== "function"
            ) return;

            cancelReservationTrigger = trigger;
            cancelReservationForm.action = trigger.dataset.cancelUrl;
            cancelReservationEquipment.textContent = trigger.dataset.reservationEquipment;
            cancelReservationDate.textContent = trigger.dataset.reservationDate;
            cancelReservationDialog.showModal();
            cancelReservationDialog.querySelector("[data-cancel-reservation-close]")?.focus();
        });
    });

    cancelReservationDialog?.querySelectorAll("[data-cancel-reservation-close]").forEach((control) => {
        control.addEventListener("click", closeCancelReservationDialog);
    });

    cancelReservationDialog?.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeCancelReservationDialog();
    });

    cancelReservationDialog?.addEventListener("click", (event) => {
        if (event.target === cancelReservationDialog) closeCancelReservationDialog();
    });

    cancelReservationDialog?.addEventListener("close", () => {
        cancelReservationTrigger?.focus();
        cancelReservationTrigger = null;
    });

    const errorSummary = document.querySelector("[data-focus-on-load]");
    errorSummary?.focus();

    document.querySelectorAll("[data-auto-dismiss='true']").forEach((message) => {
        window.setTimeout(() => {
            message.classList.add("is-dismissing");
            window.setTimeout(() => message.remove(), 220);
        }, 6000);
    });

    const reservationForm = document.querySelector("[data-reservation-form]");
    const reservationType = reservationForm?.querySelector("[data-reservation-type]");
    const reservationLocation = reservationForm?.querySelector("[data-reservation-location]");
    const reservationDate = reservationForm?.querySelector("[data-reservation-date]");
    const reservationStart = reservationForm?.querySelector("[data-reservation-start]");
    const reservationEnd = reservationForm?.querySelector("[data-reservation-end]");
    const reservationQuantity = reservationForm?.querySelector("[data-reservation-quantity]");
    const reservationQuantityField = reservationQuantity?.closest(".reservation-quantity-field");
    const availabilityLabel = reservationForm?.querySelector("[data-reservation-quantity-label]");
    const availabilityMessage = reservationForm?.querySelector("[data-reservation-availability-message]");
    const reservationSubmitButton = reservationForm?.querySelector("button[type='submit']");
    const reservationConfirmDialog = document.querySelector("[data-reservation-confirm-dialog]");
    const reservationConfirmSubmit = reservationConfirmDialog?.querySelector("[data-reservation-confirm-submit]");
    const reservationConfirmCancel = reservationConfirmDialog?.querySelector("[data-reservation-confirm-cancel]");
    const reservationConfirmClose = reservationConfirmDialog?.querySelector("[data-reservation-confirm-close]");
    const reservationConfirmEquipment = reservationConfirmDialog?.querySelector("[data-reservation-confirm-equipment]");
    const reservationConfirmQuantity = reservationConfirmDialog?.querySelector("[data-reservation-confirm-quantity]");
    const reservationConfirmLocation = reservationConfirmDialog?.querySelector("[data-reservation-confirm-location]");
    const reservationConfirmDate = reservationConfirmDialog?.querySelector("[data-reservation-confirm-date]");
    const reservationConfirmStart = reservationConfirmDialog?.querySelector("[data-reservation-confirm-start]");
    const reservationConfirmEnd = reservationConfirmDialog?.querySelector("[data-reservation-confirm-end]");
    const reservationHolidayNotice = reservationConfirmDialog?.querySelector("[data-reservation-holiday-notice]");
    const reservationHolidayTitle = reservationConfirmDialog?.querySelector("[data-reservation-holiday-title]");
    const reservationHolidayMessage = reservationConfirmDialog?.querySelector("[data-reservation-holiday-message]");
    const reservationCalendar = reservationForm?.querySelector("[data-reservation-calendar]");
    const reservationCalendarToggle = reservationCalendar?.querySelector("[data-reservation-calendar-toggle]");
    const reservationCalendarValue = reservationCalendar?.querySelector("[data-reservation-calendar-value]");
    const reservationCalendarPanel = reservationCalendar?.querySelector("[data-reservation-calendar-panel]");
    const reservationCalendarTitle = reservationCalendar?.querySelector("[data-reservation-calendar-title]");
    const reservationCalendarDays = reservationCalendar?.querySelector("[data-reservation-calendar-days]");
    const reservationCalendarPrevious = reservationCalendar?.querySelector("[data-reservation-calendar-previous]");
    const reservationCalendarNext = reservationCalendar?.querySelector("[data-reservation-calendar-next]");
    const reservationCalendarStatus = reservationCalendar?.querySelector("[data-reservation-calendar-status]");
    const reservationDateFeedback = reservationForm?.querySelector("[data-reservation-date-feedback]");
    let reservationConfirmationInProgress = false;
    let reservationHolidayConsultation = null;
    let availabilityRequest = 0;
    let calendarVisibleMonth = null;
    const calendarHolidayCache = new Map();
    const calendarHolidayRequests = new Map();

    const dataSelecionada = () => {
        if (!reservationDate?.value) return null;
        const data = reservationDate.value;
        const [ano, mes, dia] = data.split("-").map(Number);
        if (!ano || !mes || !dia) return null;
        return new Date(Date.UTC(ano, mes - 1, dia));
    };

    const eFimDeSemana = (data) => data && (data.getUTCDay() === 0 || data.getUTCDay() === 6);

    const dataUtcDoIso = (valor) => {
        if (!valor) return null;
        const [ano, mes, dia] = valor.split("-").map(Number);
        if (!ano || !mes || !dia) return null;
        return new Date(Date.UTC(ano, mes - 1, dia));
    };

    const isoDaDataUtc = (data) => [
        data.getUTCFullYear(),
        String(data.getUTCMonth() + 1).padStart(2, "0"),
        String(data.getUTCDate()).padStart(2, "0"),
    ].join("-");

    const hojeEmUtc = () => {
        const hoje = new Date();
        return new Date(Date.UTC(hoje.getFullYear(), hoje.getMonth(), hoje.getDate()));
    };

    const formatoDataCurta = new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "UTC",
    });
    const formatoDataLonga = new Intl.DateTimeFormat("pt-BR", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    });
    const formatoMes = new Intl.DateTimeFormat("pt-BR", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    });

    const feriadoNaData = (data) => {
        const feriadosDoAno = calendarHolidayCache.get(data.getUTCFullYear())?.feriados;
        return feriadosDoAno?.get(isoDaDataUtc(data)) || null;
    };

    const atualizarFeedbackDaData = () => {
        if (!reservationDateFeedback) return;
        const data = dataSelecionada();
        const feriado = data ? feriadoNaData(data) : null;
        reservationDateFeedback.hidden = !feriado;
        reservationDateFeedback.textContent = feriado
            ? `Feriado nacional: ${feriado}. A data continua disponível para reserva.`
            : "";
    };

    const atualizarExibicaoDaData = () => {
        if (!reservationCalendarValue) return;
        const data = dataSelecionada();
        reservationCalendarValue.textContent = data
            ? formatoDataCurta.format(data)
            : "Selecione uma data";
        atualizarFeedbackDaData();
    };

    const fecharCalendario = ({ devolverFoco = false } = {}) => {
        if (!reservationCalendarPanel || reservationCalendarPanel.hidden) return;
        reservationCalendarPanel.hidden = true;
        reservationCalendarToggle?.setAttribute("aria-expanded", "false");
        if (devolverFoco) reservationCalendarToggle?.focus();
    };

    const carregarFeriadosDoAno = (ano) => {
        if (!reservationCalendar?.dataset.holidaysUrl || calendarHolidayCache.has(ano)) {
            return Promise.resolve(calendarHolidayCache.get(ano));
        }
        if (calendarHolidayRequests.has(ano)) return calendarHolidayRequests.get(ano);

        const url = new URL(reservationCalendar.dataset.holidaysUrl, window.location.origin);
        url.searchParams.set("ano", String(ano));
        const requisicao = fetch(url, { headers: { Accept: "application/json" } })
            .then(async (response) => {
                const payload = await response.json();
                if (!response.ok) throw new Error(payload.erro || "Não foi possível consultar os feriados.");
                const feriados = new Map(
                    (Array.isArray(payload.feriados) ? payload.feriados : [])
                        .filter((feriado) => typeof feriado.data === "string" && typeof feriado.nome === "string")
                        .map((feriado) => [feriado.data, feriado.nome]),
                );
                const resultado = { completa: payload.completa !== false, feriados };
                calendarHolidayCache.set(ano, resultado);
                return resultado;
            })
            .catch(() => {
                const resultado = { completa: false, feriados: new Map() };
                calendarHolidayCache.set(ano, resultado);
                return resultado;
            })
            .finally(() => {
                calendarHolidayRequests.delete(ano);
                if (calendarVisibleMonth?.getUTCFullYear() === ano) renderizarCalendario();
                atualizarFeedbackDaData();
            });

        calendarHolidayRequests.set(ano, requisicao);
        return requisicao;
    };

    const dataIndisponivelNoCalendario = (data) => {
        const dataMinima = dataUtcDoIso(reservationDate?.min) || hojeEmUtc();
        return data < dataMinima || eFimDeSemana(data);
    };

    function renderizarCalendario({ focarData = "" } = {}) {
        if (!calendarVisibleMonth || !reservationCalendarDays || !reservationCalendarTitle) return;

        const ano = calendarVisibleMonth.getUTCFullYear();
        const mes = calendarVisibleMonth.getUTCMonth();
        const primeiroDia = new Date(Date.UTC(ano, mes, 1));
        const ultimoDia = new Date(Date.UTC(ano, mes + 1, 0));
        const deslocamento = (primeiroDia.getUTCDay() + 6) % 7;
        const selecionada = reservationDate?.value || "";
        const hoje = isoDaDataUtc(hojeEmUtc());
        const consulta = calendarHolidayCache.get(ano);
        const dataMinima = dataUtcDoIso(reservationDate?.min) || hojeEmUtc();
        const primeiroMesPermitido = new Date(Date.UTC(dataMinima.getUTCFullYear(), dataMinima.getUTCMonth(), 1));

        const tituloMes = formatoMes.format(primeiroDia);
        reservationCalendarTitle.textContent = tituloMes.charAt(0).toUpperCase() + tituloMes.slice(1);
        reservationCalendarDays.replaceChildren();
        reservationCalendarPrevious.disabled = primeiroDia <= primeiroMesPermitido;

        if (reservationCalendarStatus) {
            if (!consulta) {
                reservationCalendarStatus.textContent = "Consultando feriados nacionais…";
            } else if (!consulta.completa) {
                reservationCalendarStatus.textContent = "Não foi possível carregar os feriados. As demais datas continuam disponíveis.";
            } else {
                reservationCalendarStatus.textContent = "";
            }
        }

        for (let indice = 0; indice < deslocamento; indice += 1) {
            const vazio = document.createElement("span");
            vazio.className = "reservation-calendar-empty";
            vazio.setAttribute("aria-hidden", "true");
            reservationCalendarDays.append(vazio);
        }

        let primeiroDiaDisponivel = null;
        for (let dia = 1; dia <= ultimoDia.getUTCDate(); dia += 1) {
            const data = new Date(Date.UTC(ano, mes, dia));
            const dataIso = isoDaDataUtc(data);
            const feriado = feriadoNaData(data);
            const fimDeSemana = eFimDeSemana(data);
            const passada = data < dataMinima;
            const indisponivel = fimDeSemana || passada;
            const botao = document.createElement("button");
            const descricao = [formatoDataLonga.format(data)];

            botao.type = "button";
            botao.className = "reservation-calendar-day";
            botao.dataset.calendarDate = dataIso;
            botao.textContent = String(dia);
            botao.setAttribute("role", "gridcell");
            botao.tabIndex = -1;

            if (feriado) {
                botao.classList.add("is-holiday");
                descricao.push(`Feriado nacional: ${feriado}`);
            }
            if (fimDeSemana) descricao.push("Indisponível: fim de semana");
            if (passada) descricao.push("Indisponível: data passada");
            if (dataIso === hoje) botao.setAttribute("aria-current", "date");
            if (dataIso === selecionada) {
                botao.classList.add("is-selected");
                botao.setAttribute("aria-selected", "true");
            } else {
                botao.setAttribute("aria-selected", "false");
            }

            botao.setAttribute("aria-label", descricao.join(". "));
            botao.title = descricao.slice(1).join(". ");
            botao.disabled = indisponivel;
            if (indisponivel) botao.classList.add("is-unavailable");
            if (!indisponivel && !primeiroDiaDisponivel) primeiroDiaDisponivel = botao;
            reservationCalendarDays.append(botao);
        }

        const selecionadoNoMes = reservationCalendarDays.querySelector(".reservation-calendar-day.is-selected:not(:disabled)");
        const hojeNoMes = reservationCalendarDays.querySelector(".reservation-calendar-day[aria-current='date']:not(:disabled)");
        const focoPadrao = selecionadoNoMes || hojeNoMes || primeiroDiaDisponivel;
        if (focoPadrao) focoPadrao.tabIndex = 0;

        if (focarData) {
            const alvo = reservationCalendarDays.querySelector(`[data-calendar-date="${focarData}"]:not(:disabled)`)
                || focoPadrao;
            alvo?.focus();
        }
    }

    const exibirMes = (data, { focarData = "" } = {}) => {
        calendarVisibleMonth = new Date(Date.UTC(data.getUTCFullYear(), data.getUTCMonth(), 1));
        renderizarCalendario({ focarData });
        carregarFeriadosDoAno(calendarVisibleMonth.getUTCFullYear());
    };

    const abrirCalendario = () => {
        if (!reservationCalendarPanel || !reservationCalendarToggle) return;
        const base = dataSelecionada() || dataUtcDoIso(reservationDate?.min) || hojeEmUtc();
        reservationCalendarPanel.hidden = false;
        reservationCalendarToggle.setAttribute("aria-expanded", "true");
        exibirMes(base, { focarData: reservationDate?.value || isoDaDataUtc(base) });
    };

    const selecionarDataDoCalendario = (dataIso) => {
        if (!reservationDate) return;
        reservationDate.value = dataIso;
        atualizarExibicaoDaData();
        fecharCalendario({ devolverFoco: true });
        reservationDate.dispatchEvent(new Event("change", { bubbles: true }));
    };

    if (
        reservationCalendar
        && reservationDate
        && reservationCalendarToggle
        && reservationCalendarPanel
        && reservationCalendarDays
    ) {
        reservationCalendar.classList.add("is-enhanced");
        reservationDate.required = false;
        reservationDate.tabIndex = -1;
        reservationDate.setAttribute("aria-hidden", "true");
        reservationCalendarToggle.hidden = false;
        const dateLabel = reservationDate.closest(".form-field")?.querySelector("label[for]");
        if (dateLabel) dateLabel.htmlFor = reservationCalendarToggle.id;
        if (reservationDate.classList.contains("is-invalid")) {
            reservationCalendarToggle.classList.add("is-invalid");
            reservationCalendarToggle.setAttribute("aria-invalid", "true");
        }
        const describedBy = reservationDate.getAttribute("aria-describedby");
        if (describedBy) reservationCalendarToggle.setAttribute("aria-describedby", describedBy);
        atualizarExibicaoDaData();

        reservationCalendarToggle.addEventListener("click", () => {
            if (reservationCalendarPanel.hidden) abrirCalendario();
            else fecharCalendario({ devolverFoco: true });
        });
        reservationCalendarPrevious?.addEventListener("click", () => {
            if (!calendarVisibleMonth) return;
            exibirMes(new Date(Date.UTC(
                calendarVisibleMonth.getUTCFullYear(),
                calendarVisibleMonth.getUTCMonth() - 1,
                1,
            )));
        });
        reservationCalendarNext?.addEventListener("click", () => {
            if (!calendarVisibleMonth) return;
            exibirMes(new Date(Date.UTC(
                calendarVisibleMonth.getUTCFullYear(),
                calendarVisibleMonth.getUTCMonth() + 1,
                1,
            )));
        });
        reservationCalendarDays.addEventListener("click", (event) => {
            const botao = event.target.closest("[data-calendar-date]");
            if (botao && !botao.disabled) selecionarDataDoCalendario(botao.dataset.calendarDate);
        });
        reservationCalendarDays.addEventListener("keydown", (event) => {
            const botaoAtual = event.target.closest("[data-calendar-date]");
            if (!botaoAtual) return;
            const deslocamentos = {
                ArrowLeft: -1,
                ArrowRight: 1,
                ArrowUp: -7,
                ArrowDown: 7,
            };
            if (!(event.key in deslocamentos)) return;
            event.preventDefault();
            const direcao = deslocamentos[event.key];
            let alvo = dataUtcDoIso(botaoAtual.dataset.calendarDate);
            let encontrouDataDisponivel = false;
            for (let tentativa = 0; tentativa < 14; tentativa += 1) {
                alvo = new Date(alvo.getTime() + direcao * 86400000);
                if (!dataIndisponivelNoCalendario(alvo)) {
                    encontrouDataDisponivel = true;
                    break;
                }
            }
            if (!encontrouDataDisponivel) return;
            exibirMes(alvo, { focarData: isoDaDataUtc(alvo) });
        });
        reservationCalendarPanel.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                fecharCalendario({ devolverFoco: true });
            }
        });
        document.addEventListener("click", (event) => {
            if (!reservationCalendar.contains(event.target)) fecharCalendario();
        });
    }

    const bloquearQuantidade = ({ limpar = false } = {}) => {
        if (!reservationQuantity) return;
        reservationQuantity.disabled = true;
        reservationQuantity.setAttribute("aria-disabled", "true");
        reservationQuantity.removeAttribute("max");
        if (limpar) reservationQuantity.value = "";
        reservationQuantityField?.classList.add("is-disabled");
    };

    const liberarQuantidade = (disponiveis) => {
        if (!reservationQuantity || disponiveis < 1) return;
        reservationQuantity.disabled = false;
        reservationQuantity.removeAttribute("aria-disabled");
        reservationQuantity.setAttribute("max", String(disponiveis));
        reservationQuantityField?.classList.remove("is-disabled");
    };

    const redefinirDisponibilidade = (
        mensagem = "Selecione o equipamento, o local e o período para consultar.",
        { limparQuantidade = false } = {},
    ) => {
        availabilityRequest += 1;
        availabilityLabel?.classList.remove("is-success", "is-warning");
        if (availabilityLabel) availabilityLabel.textContent = "(Disponível: --)";
        if (availabilityMessage) availabilityMessage.textContent = mensagem;
        reservationHolidayConsultation = null;
        bloquearQuantidade({ limpar: limparQuantidade });
    };

    const definirErroCliente = (field, mensagem) => {
        const error = reservationForm?.querySelector(`[data-reservation-error-for="${field.name}"]`);
        if (!error) return;
        error.textContent = mensagem;
        error.hidden = !mensagem;
        const visualField = field === reservationDate && reservationCalendar?.classList.contains("is-enhanced")
            ? reservationCalendarToggle
            : field;
        if (mensagem) {
            field.dataset.weekendInvalid = "true";
            field.classList.add("is-invalid");
            field.setAttribute("aria-invalid", "true");
            visualField?.classList.add("is-invalid");
            visualField?.setAttribute("aria-invalid", "true");
        } else if (field.dataset.weekendInvalid) {
            delete field.dataset.weekendInvalid;
            field.removeAttribute("aria-invalid");
            field.classList.remove("is-invalid");
            visualField?.removeAttribute("aria-invalid");
            visualField?.classList.remove("is-invalid");
        }
    };

    const validarPeriodoDaReserva = ({ limparDiaInvalido = true, focarErro = false, exigirData = false } = {}) => {
        const data = dataSelecionada();

        definirErroCliente(reservationDate, "");
        definirErroCliente(reservationStart, "");
        definirErroCliente(reservationEnd, "");

        if (exigirData && !data) {
            definirErroCliente(reservationDate, "Selecione a data da reserva.");
            if (focarErro) (reservationCalendarToggle || reservationDate)?.focus();
            return false;
        }

        if (eFimDeSemana(data)) {
            definirErroCliente(reservationDate, "Sábados e domingos não estão disponíveis para reserva.");
            if (limparDiaInvalido) {
                reservationDate.value = "";
                atualizarExibicaoDaData();
            }
            if (focarErro) (reservationCalendarToggle || reservationDate)?.focus();
            return false;
        }

        if (reservationDate?.value && reservationStart?.value) {
            const inicio = new Date(`${reservationDate.value}T${reservationStart.value}:00`);
            if (inicio < new Date()) {
                definirErroCliente(
                    reservationStart,
                    "A data e a hora inicial da reserva não podem estar no passado.",
                );
                if (focarErro) reservationStart.focus();
                return false;
            }
        }

        if (
            reservationStart?.value
            && reservationEnd?.value
            && reservationEnd.value <= reservationStart.value
        ) {
            definirErroCliente(
                reservationEnd,
                "A hora final deve ser posterior ao inicio da reserva",
            );
            if (focarErro) reservationEnd.focus();
            return false;
        }

        return true;
    };

    const consultarDisponibilidade = async ({ limparQuantidade = false } = {}) => {
        if (
            !reservationType?.value
            || !reservationLocation?.value
            || !reservationDate?.value
            || !reservationStart?.value
            || !reservationEnd?.value
        ) {
            redefinirDisponibilidade(undefined, { limparQuantidade });
            return;
        }

        const requestId = ++availabilityRequest;
        bloquearQuantidade({ limpar: limparQuantidade });
        availabilityLabel?.classList.remove("is-success", "is-warning");
        if (availabilityLabel) availabilityLabel.textContent = "(Consultando...)";
        if (availabilityMessage) availabilityMessage.textContent = "Consultando unidades disponíveis…";
        const params = new URLSearchParams({
            tipo_equipamento: reservationType.value,
            local: reservationLocation.value,
            data_reserva: reservationDate.value,
            hora_inicio: reservationStart.value,
            hora_fim: reservationEnd.value,
        });

        try {
            const response = await fetch(`${reservationForm.dataset.availabilityUrl}?${params}`, {
                headers: { Accept: "application/json" },
            });
            const payload = await response.json();
            if (requestId !== availabilityRequest) return;
            if (!response.ok) throw new Error(payload.erro || "Não foi possível consultar a disponibilidade.");
            const disponiveis = Number(payload.disponiveis);
            reservationHolidayConsultation = payload.consulta_feriados;
            availabilityLabel?.classList.toggle("is-success", disponiveis > 0);
            availabilityLabel?.classList.toggle("is-warning", disponiveis === 0);
            if (availabilityLabel) availabilityLabel.textContent = `(Disponível: ${disponiveis})`;
            if (availabilityMessage) availabilityMessage.textContent = disponiveis
                ? `${disponiveis} unidade(s) disponível(is) para o período informado.`
                : "Nenhuma unidade disponível para o período informado.";
            if (disponiveis > 0) {
                liberarQuantidade(disponiveis);
            } else {
                bloquearQuantidade({ limpar: true });
            }
        } catch (error) {
            if (requestId !== availabilityRequest) return;
            availabilityLabel?.classList.add("is-warning");
            if (availabilityLabel) availabilityLabel.textContent = "(Disponibilidade indisponível)";
            if (availabilityMessage) availabilityMessage.textContent = error.message;
            bloquearQuantidade({ limpar: true });
        }
    };

    const preencherAvisoFeriado = () => {
        if (!reservationHolidayNotice) return;

        reservationHolidayNotice.hidden = true;
        const feriados = Array.isArray(reservationHolidayConsultation?.feriados)
            ? reservationHolidayConsultation.feriados
            : [];

        if (feriados.length) {
            const descricao = feriados.map((feriado) => {
                const data = typeof feriado.data === "string"
                    ? feriado.data.split("-").reverse().join("/")
                    : "data não informada";
                return `${feriado.nome} (${data})`;
            }).join(", ");

            if (reservationHolidayTitle) {
                reservationHolidayTitle.textContent = "A data selecionada coincide com feriado nacional.";
            }
            if (reservationHolidayMessage) {
                reservationHolidayMessage.textContent = `${descricao}. O aviso é informativo; você ainda pode confirmar a reserva.`;
            }
            reservationHolidayNotice.hidden = false;
            return;
        }

        if (reservationHolidayConsultation?.completa === false) {
            if (reservationHolidayTitle) {
                reservationHolidayTitle.textContent = "Não foi possível consultar os feriados nacionais.";
            }
            if (reservationHolidayMessage) {
                reservationHolidayMessage.textContent = "A consulta à BrasilAPI não foi concluída, mas você ainda pode confirmar a reserva.";
            }
            reservationHolidayNotice.hidden = false;
        }
    };

    const preencherConfirmacaoReserva = () => {
        const data = reservationDate?.value
            ? reservationDate.value.split("-").reverse().join("/")
            : "—";
        const equipamento = reservationType?.selectedOptions?.[0]?.textContent?.trim() || "—";
        const local = reservationLocation?.selectedOptions?.[0]?.textContent?.trim() || "—";

        if (reservationConfirmEquipment) reservationConfirmEquipment.textContent = equipamento;
        if (reservationConfirmQuantity) reservationConfirmQuantity.textContent = reservationQuantity?.value || "—";
        if (reservationConfirmLocation) reservationConfirmLocation.textContent = local;
        if (reservationConfirmDate) reservationConfirmDate.textContent = data;
        if (reservationConfirmStart) reservationConfirmStart.textContent = reservationStart?.value || "—";
        if (reservationConfirmEnd) reservationConfirmEnd.textContent = reservationEnd?.value || "—";
        preencherAvisoFeriado();
    };

    const fecharConfirmacaoReserva = () => {
        if (reservationConfirmDialog?.open) reservationConfirmDialog.close();
    };

    [reservationType, reservationLocation, reservationDate, reservationStart, reservationEnd].forEach((field) => {
        field?.addEventListener("change", () => {
            if (validarPeriodoDaReserva()) {
                consultarDisponibilidade({ limparQuantidade: true });
            } else {
                redefinirDisponibilidade(
                    "Corrija o período para consultar a disponibilidade.",
                    { limparQuantidade: true },
                );
            }
        });
    });
    reservationForm?.addEventListener("submit", (event) => {
        if (reservationConfirmationInProgress) {
            reservationConfirmationInProgress = false;
            return;
        }

        if (!validarPeriodoDaReserva({ limparDiaInvalido: false, focarErro: true, exigirData: true })) {
            event.preventDefault();
            return;
        }

        if (reservationQuantity?.disabled) {
            event.preventDefault();
            if (availabilityMessage) {
                availabilityMessage.textContent = "Aguarde a consulta de disponibilidade antes de informar a quantidade.";
            }
            return;
        }

        if (reservationConfirmDialog && typeof reservationConfirmDialog.showModal === "function") {
            event.preventDefault();
            preencherConfirmacaoReserva();
            reservationConfirmDialog.showModal();
            reservationConfirmSubmit?.focus();
        }
    });

    reservationConfirmSubmit?.addEventListener("click", () => {
        if (!reservationForm) return;
        reservationConfirmationInProgress = true;
        fecharConfirmacaoReserva();
        reservationForm.requestSubmit();
    });

    [reservationConfirmCancel, reservationConfirmClose].forEach((control) => {
        control?.addEventListener("click", fecharConfirmacaoReserva);
    });

    reservationConfirmDialog?.addEventListener("cancel", (event) => {
        event.preventDefault();
        fecharConfirmacaoReserva();
    });

    reservationConfirmDialog?.addEventListener("click", (event) => {
        if (event.target === reservationConfirmDialog) fecharConfirmacaoReserva();
    });

    reservationConfirmDialog?.addEventListener("close", () => {
        if (!reservationConfirmationInProgress) reservationSubmitButton?.focus();
    });

    consultarDisponibilidade();
});
