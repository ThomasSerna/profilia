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

const DROP_HIGHLIGHT = ["ring-2", "ring-[#02bc4d]", "bg-emerald-50"];
const DRAG_THRESHOLD = 6;
const TOUCH_HOLD_MS = 250;
const INTERACTIVE = "button, a, input, select, textarea, summary, details";

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
    const statusLine = document.getElementById("followup-status");
    const notificationList = document.getElementById("notification-list");
    const notificationSummary = document.getElementById("notification-summary");
    const counter = document.getElementById("notification-counter");
    const readAllButton = document.getElementById("read-all-button");
    const dataElement = document.getElementById("followup-board-data");

    if (!page || !boardElement || !notificationList) {
        return;
    }

    const csrfToken = page.querySelector("[name=csrfmiddlewaretoken]").value;
    let board = JSON.parse(dataElement?.textContent || "{}");
    let busy = false;
    let drag = null;

    readAllButton.addEventListener("click", () => send(page.dataset.readAllUrl));
    // Mientras se arrastra con el dedo, evita que la página se desplace.
    document.addEventListener("touchmove", event => {
        if (drag?.active) {
            event.preventDefault();
        }
    }, { passive: false });

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
        busy = true;
        setStatus("Revisando tus postulaciones...");
        try {
            board = (await post(page.dataset.runUrl)).board;
            setStatus("Tus recordatorios y próximos pasos están al día.");
        } catch (error) {
            setStatus(connectionMessage(error), true);
        } finally {
            busy = false;
            render();
        }
    }

    async function send(url, data, successText, previous = null) {
        if (busy) {
            return;
        }
        busy = true;
        render();
        try {
            board = (await post(url, data)).board;
            if (successText) {
                setStatus(successText);
            }
        } catch (error) {
            if (previous) {
                board = previous;
            }
            setStatus(connectionMessage(error), true);
        } finally {
            busy = false;
            render();
        }
    }

    function moveTo(item, status) {
        const target = COLUMNS.find(column => column.status === status);
        if (!target || status === item.status || busy) {
            return;
        }
        // Se mueve en pantalla de inmediato; el servidor confirma y devuelve el tablero actualizado.
        // Si falla, la tarjeta vuelve a su etapa anterior.
        const previous = board;
        board = {
            ...board,
            applications: board.applications.map(app => app.id === item.id
                ? { ...app, status, status_label: target.label, next_step: "", reminders: [] } : app),
        };
        setStatus(`Actualizando ${item.title}...`);
        send(page.dataset.moveUrl.replace("/0/", `/${item.id}/`), { status },
            `Moviste ${item.title} a ${target.label}.`, previous);
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
            const section = element("section", `rounded-xl bg-slate-50 border border-slate-200 border-t-4 ${column.accent} p-3 space-y-3 min-h-[160px] transition-colors`);
            section.dataset.status = column.status;
            section.setAttribute("aria-label", column.label);
            const header = element("div", "flex items-center justify-between gap-2");
            const title = element("h3", "text-xs font-bold text-[#13223a] flex items-center gap-2");
            title.append(icon(`${column.icon} text-[#02bc4d]`), element("span", "", column.label));
            header.append(title, element("span", "text-[10px] font-semibold text-slate-500", plural(items.length, "postulación", "postulaciones")));
            section.append(header);
            if (!items.length) {
                section.append(element("p", "text-[11px] text-slate-400 border border-dashed border-slate-300 rounded-lg p-3 text-center", "Arrastra aquí una postulación."));
            }
            items.forEach(item => section.append(buildCard(item)));
            return section;
        }));
    }

    function buildCard(item) {
        const card = element("article", `p-3 rounded-xl border border-slate-200 bg-white space-y-2.5 text-xs shadow-sm select-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#008736] ${busy ? "cursor-wait" : "cursor-grab"}`);
        card.tabIndex = 0;
        card.setAttribute("aria-label", `${item.title} en ${item.company}, etapa ${item.status_label}. Arrastra la tarjeta o usa las flechas izquierda y derecha para cambiar de etapa.`);
        card.addEventListener("pointerdown", event => startDrag(event, card, item));
        card.addEventListener("keydown", event => {
            if (event.target !== card || (event.key !== "ArrowRight" && event.key !== "ArrowLeft")) {
                return;
            }
            event.preventDefault();
            const index = COLUMNS.findIndex(column => column.status === item.status);
            const next = COLUMNS[index + (event.key === "ArrowRight" ? 1 : -1)];
            if (next) {
                moveTo(item, next.status);
            }
        });

        const header = element("div", "flex items-start justify-between gap-2");
        const titleBox = element("div", "min-w-0 flex items-start gap-2");
        const texts = element("div", "min-w-0");
        texts.append(
            element("p", "font-bold text-[#13223a] text-sm break-words", item.title),
            element("p", "text-slate-500 break-words", item.company),
        );
        titleBox.append(icon("fa-grip-vertical text-slate-300 mt-1"), texts);
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

        return card;
    }

    function startDrag(event, card, item) {
        if (busy || event.button > 0 || event.target.closest(INTERACTIVE)) {
            return;
        }
        drag = { card, item, startX: event.clientX, startY: event.clientY, active: false, ghost: null, over: null, timer: null };
        if (event.pointerType === "touch") {
            // En pantallas táctiles se mantiene presionada la tarjeta para no confundir el gesto con el scroll.
            drag.timer = setTimeout(() => activateDrag(event.clientX, event.clientY), TOUCH_HOLD_MS);
        }
        card.setPointerCapture?.(event.pointerId);
        card.addEventListener("pointermove", onDragMove);
        card.addEventListener("pointerup", onDragEnd);
        card.addEventListener("pointercancel", cancelDrag);
    }

    function activateDrag(x, y) {
        if (!drag || drag.active) {
            return;
        }
        const rect = drag.card.getBoundingClientRect();
        const ghost = drag.card.cloneNode(true);
        ghost.removeAttribute("tabindex");
        ghost.setAttribute("aria-hidden", "true");
        ghost.style.cssText = `position:fixed;left:0;top:0;width:${rect.width}px;pointer-events:none;z-index:50;opacity:.95;`;
        ghost.classList.add("shadow-xl", "rotate-2", "cursor-grabbing");
        document.body.append(ghost);
        drag = { ...drag, active: true, ghost, offsetX: x - rect.left, offsetY: y - rect.top };
        drag.card.classList.add("opacity-40");
        positionGhost(x, y);
    }

    function onDragMove(event) {
        if (!drag) {
            return;
        }
        const distance = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
        if (!drag.active) {
            if (event.pointerType === "touch") {
                if (distance > DRAG_THRESHOLD) {
                    cancelDrag();
                }
                return;
            }
            if (distance < DRAG_THRESHOLD) {
                return;
            }
            activateDrag(event.clientX, event.clientY);
        }
        positionGhost(event.clientX, event.clientY);
        highlight(columnAt(event.clientX, event.clientY));
    }

    function onDragEnd(event) {
        if (!drag) {
            return;
        }
        const { active, item } = drag;
        const column = active ? columnAt(event.clientX, event.clientY) : null;
        cancelDrag();
        if (column) {
            moveTo(item, column.dataset.status);
        }
    }

    function cancelDrag() {
        if (!drag) {
            return;
        }
        clearTimeout(drag.timer);
        drag.ghost?.remove();
        drag.card.classList.remove("opacity-40");
        drag.card.removeEventListener("pointermove", onDragMove);
        drag.card.removeEventListener("pointerup", onDragEnd);
        drag.card.removeEventListener("pointercancel", cancelDrag);
        highlight(null);
        drag = null;
    }

    function positionGhost(x, y) {
        drag.ghost.style.transform = `translate(${x - drag.offsetX}px, ${y - drag.offsetY}px) rotate(2deg)`;
    }

    function columnAt(x, y) {
        return document.elementFromPoint(x, y)?.closest("#followup-board [data-status]") || null;
    }

    function highlight(column) {
        if (drag?.over === column) {
            return;
        }
        drag?.over?.classList.remove(...DROP_HIGHLIGHT);
        if (column && column.dataset.status !== drag?.item.status) {
            column.classList.add(...DROP_HIGHLIGHT);
        }
        if (drag) {
            drag.over = column;
        }
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

    function setStatus(text, isError = false) {
        statusLine.textContent = text;
        statusLine.className = `text-xs ${isError ? "text-red-700" : "text-slate-600"}`;
    }

    function connectionMessage(error) {
        return error instanceof TypeError ? "No pudimos conectar con Profilia. Intenta de nuevo." : error.message;
    }
}

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initFollowup);
}
