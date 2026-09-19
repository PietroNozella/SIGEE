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
    let reservationConfirmationInProgress = false;
    let availabilityRequest = 0;

    const dataSelecionada = () => {
        if (!reservationDate?.value) return null;
        const data = reservationDate.value;
        const [ano, mes, dia] = data.split("-").map(Number);
        if (!ano || !mes || !dia) return null;
        return new Date(Date.UTC(ano, mes - 1, dia));
    };

    const eFimDeSemana = (data) => data && (data.getUTCDay() === 0 || data.getUTCDay() === 6);

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
        bloquearQuantidade({ limpar: limparQuantidade });
    };

    const definirErroCliente = (field, mensagem) => {
        const error = reservationForm?.querySelector(`[data-reservation-error-for="${field.name}"]`);
        if (!error) return;
        error.textContent = mensagem;
        error.hidden = !mensagem;
        if (mensagem) {
            field.dataset.weekendInvalid = "true";
            field.classList.add("is-invalid");
            field.setAttribute("aria-invalid", "true");
        } else if (field.dataset.weekendInvalid) {
            delete field.dataset.weekendInvalid;
            field.removeAttribute("aria-invalid");
            field.classList.remove("is-invalid");
        }
    };

    const validarPeriodoDaReserva = ({ limparDiaInvalido = true, focarErro = false } = {}) => {
        const data = dataSelecionada();

        definirErroCliente(reservationDate, "");
        definirErroCliente(reservationStart, "");
        definirErroCliente(reservationEnd, "");

        if (eFimDeSemana(data)) {
            definirErroCliente(reservationDate, "Sábados e domingos não estão disponíveis para reserva.");
            if (limparDiaInvalido) reservationDate.value = "";
            if (focarErro) reservationDate?.focus();
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

        if (!validarPeriodoDaReserva({ limparDiaInvalido: false, focarErro: true })) {
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
