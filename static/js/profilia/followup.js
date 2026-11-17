const COLUMNS = [
    { status: "postulada", label: "Postulada", icon: "fa-paper-plane", accent: "border-t-slate-400" },
    { status: "en_revision", label: "En revisión", icon: "fa-magnifying-glass", accent: "border-t-sky-500" },
    { status: "entrevista", label: "Entrevista", icon: "fa-comments", accent: "border-t-[#02bc4d]" },
    { status: "descartada", label: "Descartada", icon: "fa-circle-xmark", accent: "border-t-slate-300" },
];

const STATUS_BADGES = {
    postulada: "bg-slate-100 text-slate-700 border-slate-200",
    en_revision: "bg-sky-100 text-sky-800 border-sky-200",
    entrevista: "bg-emerald-100 text-[#02bc4d] border-emerald-200",
    descartada: "bg-slate-200 text-slate-500 border-slate-300",
};

const EVENT_CLASSES = {
    system: "text-slate-400",
    agent: "text-emerald-400",
    step: "text-slate-300",
    success: "text-emerald-400",
    final: "text-amber-300 font-bold",
    warning: "text-amber-300",
    error: "text-red-400 font-bold",
};

export function plural(count, singular, pluralForm) {
    return `${count} ${count === 1 ? singular : (pluralForm || `${singular}s`)}`;
}

function formatDate(value) {
    if (!value) {
        return "";
    }
    const date = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
    return date.toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" });
}

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}

function icon(name) {
    const node = element("i", `fa-solid ${name}`);
    node.setAttribute("aria-hidden", "true");
    return node;
}

export function initFollowup() {
    const page = document.getElementById("followup-page");
    const boardElement = document.getElementById("followup-board");
    const consoleBox = document.getElementById("followup-console");
    const statusLine = document.getElementById("followup-status");
    const agentState = document.getElementById("followup-agent-state");
    const notificationList = document.getElementById("notification-list");
    const notificationSummary = document.getElementById("notification-summary");
    const counter = document.getElementById("notification-counter");
    const readAllButton = document.getElementById("read-all-button");
    const dataElement = document.getElementById("followup-board-data");

    if (!page || !boardElement || !consoleBox || !notificationList) {
        return;
    }

    const csrfToken = page.querySelector("[name=csrfmiddlewaretoken]").value;
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let board = JSON.parse(dataElement?.textContent || "{}");
    let busy = false;

    readAllButton.addEventListener("click", () => send(page.dataset.readAllUrl));

    render();
    runAgent();

    async function post(url, data = {}) {
        const body = new FormData();
        Object.entries(data).forEach(([key, value]) => body.append(key, value));
        const response = await fetch(url, {
            method: "POST",
            body,
            headers: { "X-CSRFToken": csrfToken },
            credentials: "same-origin",
        });
        const payload = await response.json().catch(() => ({ success: false, error: "Respuesta no válida." }));
        if (!response.ok || !payload.success) {
            throw new Error(payload.error || "No pudimos actualizar el seguimiento.");
        }
        return payload;
    }

    // El evento POSTULACIÓN ENVIADA activa el agente al entrar a la página.
    async function runAgent() {
        setBusy(true, "Revisando tus postulaciones...");
        consoleBox.replaceChildren(logLine("agent", "[AGENTE] Iniciando Agente de Seguimiento con LangGraph Agent..."));
        try {
            const data = await post(page.dataset.runUrl);
            await replay(data.events.slice(1));
            board = data.board;
            setStatus("Tus recordatorios y próximos pasos están al día.");
        } catch (error) {
            consoleBox.append(logLine("error", `[ERROR] ${error.message}`));
            setStatus(connectionMessage(error), true);
        } finally {
            setBusy(false);
            render();
        }
    }

    async function send(url, data, successText) {
        if (busy) {
            return;
        }
        setBusy(true);
        try {
            const payload = await post(url, data);
            board = payload.board;
            if (payload.events?.length) {
                consoleBox.append(logLine("system", "[SISTEMA] ESTADO CAMBIADO: el agente actualiza tus recordatorios..."));
                await replay(payload.events.slice(1));
            }
            if (successText) {
                setStatus(successText);
            }
        } catch (error) {
            setStatus(connectionMessage(error), true);
        } finally {
            setBusy(false);
            render();
        }
    }

    async function replay(events) {
        for (const item of events) {
            consoleBox.append(logLine(item.level, item.message));
            consoleBox.scrollTop = consoleBox.scrollHeight;
            if (!reducedMotion) {
                await new Promise(resolve => setTimeout(resolve, 250));
            }
        }
    }

    function render() {
        renderBoard();
        renderNotifications();
        updateSidebarBadge();
    }

    function renderBoard() {
        const applications = board.applications || [];
        boardElement.replaceChildren(...COLUMNS.map(column => {
            const items = applications.filter(item => item.status === column.status);
            const section = element("section", `rounded-xl bg-slate-50 border border-slate-200 border-t-4 ${column.accent} p-3 space-y-3 min-h-[160px]`);
            section.setAttribute("aria-label", column.label);
            const header = element("div", "flex items-center justify-between gap-2");
            const title = element("h3", "text-xs font-bold text-[#13223a] flex items-center gap-2");
            title.append(icon(`${column.icon} text-[#02bc4d]`), element("span", "", column.label));
            header.append(title, element("span", "text-[10px] font-semibold text-slate-500", plural(items.length, "postulación", "postulaciones")));
            section.append(header);
            if (!items.length) {
                section.append(element("p", "text-[11px] text-slate-400 border border-dashed border-slate-300 rounded-lg p-3 text-center", "Sin postulaciones en esta etapa."));
            }
            items.forEach(item => section.append(buildCard(item)));
            return section;
        }));
    }

    function buildCard(item) {
        const card = element("article", "p-3 rounded-xl border border-slate-200 bg-white space-y-2.5 text-xs shadow-sm");

        const header = element("div", "flex items-start justify-between gap-2");
        const titleBox = element("div", "min-w-0");
        titleBox.append(
            element("p", "font-bold text-[#13223a] text-sm break-words", item.title),
            element("p", "text-slate-500 break-words", item.company),
        );
        header.append(titleBox, element("span", "px-2 py-0.5 rounded-full border bg-white text-[#13223a] border-slate-200 text-[10px] font-black shrink-0", `${item.score}% MATCH`));
        card.append(header);

        const meta = element("div", "flex flex-wrap items-center gap-2 text-[10px]");
        meta.append(
            element("span", `px-2 py-0.5 rounded border font-bold ${STATUS_BADGES[item.status] || STATUS_BADGES.postulada}`, item.status_label),
            element("span", "text-slate-500", `Enviada el ${formatDate(item.submitted_at)}`),
        );
        card.append(meta);

        if (item.next_step) {
            const step = element("div", "p-2 rounded-lg bg-emerald-50 border border-emerald-100 space-y-0.5");
            step.append(
                element("p", "text-[10px] font-bold uppercase tracking-wide text-[#02bc4d]", "Próximo paso"),
                element("p", "text-slate-700 leading-relaxed", item.next_step),
            );
            card.append(step);
        }

        const pending = item.reminders.filter(reminder => reminder.status === "pendiente");
        const done = item.reminders.filter(reminder => reminder.status === "completado");
        if (item.reminders.length) {
            const box = element("div", "space-y-1.5");
            box.append(element("p", "text-[10px] font-bold uppercase tracking-wide text-slate-500",
                pending.length ? `Recordatorios · ${plural(pending.length, "pendiente")}` : "Recordatorios completados"));
            const list = element("ul", "space-y-1.5");
            pending.forEach(reminder => list.append(reminderRow(reminder)));
            done.forEach(reminder => list.append(reminderRow(reminder)));
            box.append(list);
            card.append(box);
        }

        const last = item.last_activity;
        if (last) {
            const activity = element("p", "text-[10px] text-slate-500 leading-relaxed");
            const who = last.source === "usuario" ? "Tú" : "Agente";
            activity.append(icon("fa-clock-rotate-left mr-1"),
                document.createTextNode(`Última actividad (${formatDate(last.created_at)} · ${who}): ${last.reason}`));
            card.append(activity);
        }

        if ((item.history || []).length) {
            const details = element("details", "rounded-lg border border-slate-200");
            details.append(element("summary", "px-2.5 py-2 min-h-[44px] flex items-center cursor-pointer font-semibold text-[#13223a] text-[11px]",
                `Historial (${plural(item.history.length, "cambio")})`));
            const list = element("ol", "px-2.5 pb-2.5 space-y-1.5");
            item.history.slice().reverse().forEach(change => {
                const row = element("li", "text-[10px] text-slate-600");
                row.append(
                    element("p", "font-semibold text-slate-700", `${formatDate(change.created_at)} · ${change.from_label} → ${change.to_label}`),
                    element("p", "", change.reason),
                );
                list.append(row);
            });
            details.append(list);
            card.append(details);
        }

        card.append(moveForm(item));
        return card;
    }

    function reminderRow(reminder) {
        const isDone = reminder.status === "completado";
        const row = element("li", `flex items-start justify-between gap-2 p-2 rounded-lg border ${isDone ? "bg-slate-50 border-slate-100" : "bg-white border-slate-200"}`);
        const text = element("div", "min-w-0");
        text.append(
            element("p", `font-semibold break-words ${isDone ? "line-through text-slate-400" : "text-slate-700"}`, reminder.title),
            element("p", "text-[10px] text-slate-500", `${isDone ? "Completado" : "Para el"} ${isDone ? "" : formatDate(reminder.due_date)}`.trim()),
        );
        if (reminder.detail && !isDone) {
            text.append(element("p", "text-[10px] text-slate-500 break-words", reminder.detail));
        }
        row.append(text);
        if (!isDone) {
            const button = element("button", "shrink-0 w-11 h-11 -m-1 rounded-lg text-[#02bc4d] hover:bg-emerald-50 flex items-center justify-center disabled:text-slate-300");
            button.type = "button";
            button.disabled = busy;
            button.setAttribute("aria-label", `Marcar como completado: ${reminder.title}`);
            button.title = "Marcar como completado";
            button.append(icon("fa-circle-check text-base"));
            button.addEventListener("click", () => send(
                page.dataset.reminderUrl.replace("/0/", `/${reminder.id}/`), {}, "Recordatorio completado."));
            row.append(button);
        }
        return row;
    }

    function moveForm(item) {
        const form = element("form", "flex items-center gap-2 pt-1 border-t border-slate-100");
        const id = `move-${item.id}`;
        const label = element("label", "sr-only", `Mover ${item.title} a otra etapa`);
        label.htmlFor = id;
        const select = element("select", "flex-1 min-w-0 min-h-[44px] rounded-lg border border-slate-200 bg-white px-2 text-[11px] text-slate-700");
        select.id = id;
        select.name = "status";
        COLUMNS.filter(column => column.status !== item.status).forEach(column => {
            const option = element("option", "", `Mover a ${column.label}`);
            option.value = column.status;
            select.append(option);
        });
        const button = element("button", "min-h-[44px] px-3 rounded-lg bg-[#13223a] hover:bg-slate-800 text-white text-[11px] font-bold disabled:bg-slate-200 disabled:text-slate-400", "Mover");
        button.type = "submit";
        button.disabled = busy;
        form.append(label, select, button);
        form.addEventListener("submit", event => {
            event.preventDefault();
            const target = COLUMNS.find(column => column.status === select.value);
            send(page.dataset.moveUrl.replace("/0/", `/${item.id}/`), { status: select.value },
                `Moviste ${item.title} a ${target ? target.label : "otra etapa"}.`);
        });
        return form;
    }

    function renderNotifications() {
        const notifications = board.notifications || [];
        const unread = board.unread_count || 0;
        counter.textContent = String(unread);
        counter.classList.toggle("hidden", unread === 0);
        counter.setAttribute("aria-label", board.unread_label || "");
        readAllButton.disabled = busy || unread === 0;
        notificationSummary.textContent = notifications.length
            ? (unread ? `Tienes ${board.unread_label}.` : "Estás al día con tus notificaciones.")
            : "Aquí verás cada cambio de estado de tus postulaciones.";

        notificationList.replaceChildren(...notifications.map(notification => {
            const row = element("li", `flex items-start justify-between gap-3 p-3 rounded-xl border text-xs ${notification.is_read ? "bg-white border-slate-200" : "bg-emerald-50 border-emerald-200"}`);
            const text = element("div", "min-w-0 space-y-0.5");
            text.append(
                element("p", `font-bold break-words ${notification.is_read ? "text-slate-600" : "text-[#13223a]"}`, notification.title),
                element("p", "text-slate-600 break-words leading-relaxed", notification.message),
                element("p", "text-[10px] text-slate-400", formatDate(notification.created_at)),
            );
            row.append(text);
            if (notification.is_read) {
                row.append(element("span", "shrink-0 text-[10px] text-slate-400 font-semibold", "Leída"));
            } else {
                const button = element("button", "shrink-0 min-h-[44px] px-2.5 rounded-lg text-[11px] font-semibold text-[#02bc4d] hover:bg-white disabled:text-slate-300", "Marcar como leída");
                button.type = "button";
                button.disabled = busy;
                button.addEventListener("click", () => send(page.dataset.readUrl.replace("/0/", `/${notification.id}/`)));
                row.append(button);
            }
            return row;
        }));
    }

    function updateSidebarBadge() {
        const badge = document.getElementById("followup-nav-badge");
        if (!badge) {
            return;
        }
        const unread = board.unread_count || 0;
        badge.dataset.unread = String(unread);
        badge.setAttribute("aria-label", board.unread_label || "");
        badge.replaceChildren();
        if (unread) {
            badge.append(icon("fa-bell text-[9px] mr-1"), document.createTextNode(`${unread} ${unread === 1 ? "nueva" : "nuevas"}`));
            badge.className = "text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 font-semibold bg-amber-400 text-[#13223a]";
        } else {
            badge.textContent = "Disponible";
            badge.className = "text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 font-semibold bg-white/20 text-white border border-white/30";
        }
    }

    function setBusy(value, text) {
        busy = value;
        agentState.replaceChildren(icon(value ? "fa-spinner fa-spin mr-1" : "fa-robot mr-1"),
            document.createTextNode(value ? "Agente trabajando" : "Agente listo"));
        agentState.className = `text-[11px] px-2.5 py-1 rounded-full font-semibold whitespace-nowrap self-start sm:self-auto border ${value ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-emerald-50 text-[#02bc4d] border-emerald-200"}`;
        if (text) {
            setStatus(text);
        }
        if (value) {
            render();
        }
    }

    function setStatus(text, isError = false) {
        statusLine.textContent = text;
        statusLine.className = `text-xs ${isError ? "text-red-700" : "text-slate-600"}`;
    }

    function connectionMessage(error) {
        return error instanceof TypeError ? "No pudimos conectar con Profilia. Intenta de nuevo." : error.message;
    }

    function logLine(level, text) {
        return element("p", EVENT_CLASSES[level] || EVENT_CLASSES.step, text);
    }
}

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initFollowup);
}
