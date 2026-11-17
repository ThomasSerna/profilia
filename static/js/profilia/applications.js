import { markApplicationsCompleted } from "./sidebar.js";

const STATUS = {
    seleccionada: {
        label: "Pendiente",
        classes: "bg-slate-200 text-slate-600 border-slate-300",
    },
    postulada: {
        label: "Postulado ✓",
        classes: "bg-emerald-100 text-[#02bc4d] border-emerald-200",
    },
    en_revision: {
        label: "En revisión",
        classes: "bg-sky-100 text-sky-800 border-sky-200",
    },
    entrevista: {
        label: "Entrevista",
        classes: "bg-emerald-100 text-[#02bc4d] border-emerald-200",
    },
    descartada: {
        label: "Descartada",
        classes: "bg-slate-200 text-slate-600 border-slate-300",
    },
};

// Estados de una postulación ya enviada (el Agente de Seguimiento la hace avanzar).
const SUBMITTED = new Set(["postulada", "en_revision", "entrevista", "descartada"]);

function unlockFollowupLink() {
    const locked = document.getElementById("followup-link-locked");
    if (!locked) {
        return;
    }
    const link = element("a", "py-3 px-6 min-h-[44px] rounded-xl bg-[#13223a] hover:bg-slate-800 text-white font-bold text-xs transition flex items-center gap-2 shadow-md");
    link.id = "followup-link";
    link.href = locked.dataset.followupUrl;
    const icon = element("i", "fa-solid fa-arrow-right text-[10px]");
    icon.setAttribute("aria-hidden", "true");
    link.append(element("span", "", "Ir a Seguimiento"), icon);
    locked.replaceWith(link);
}

const LETTER_ORIGINS = {
    groq: "Carta redactada por Profilia",
    usuario: "Carta editada por ti",
};

const SCREENING_LABELS = {
    cumple: "Con respaldo en tu perfil",
    sin_evidencia: "Sin información en tu perfil",
    informativa: "Según tus preferencias",
};

export function initApplications() {
    const page = document.getElementById("application-page");
    const form = document.getElementById("application-run-form");
    const startButton = document.getElementById("start-applications-button");
    const statusLine = document.getElementById("application-status");
    const emptyState = document.getElementById("application-empty");
    const list = document.getElementById("application-list");
    const savedElement = document.getElementById("saved-applications");

    if (!page || !form || !startButton || !list) {
        return;
    }

    const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
    let applications = JSON.parse(savedElement?.textContent || "[]");
    let running = false;
    // Cartas desplegadas: se mantienen abiertas al volver a pintar la lista.
    const openLetters = new Set();
    const editor = initLetterEditor();

    form.addEventListener("submit", event => {
        event.preventDefault();
        run();
    });

    render();

    async function run() {
        if (running || !pendingCount()) {
            return;
        }
        running = true;
        setStatus("Preparando tus postulaciones...");
        updateButton();

        try {
            const response = await fetch(page.dataset.runUrl, {
                method: "POST",
                body: new FormData(form),
                headers: { "X-CSRFToken": csrfToken },
                credentials: "same-origin",
            });
            const data = await response.json().catch(() => ({ success: false, error: "Respuesta no válida." }));

            if (!response.ok || !data.success) {
                throw new Error(data.error || "No pudimos preparar tus postulaciones.");
            }

            const done = new Map(data.applications.map(item => [item.vacancy_id, item]));
            applications = applications
                .filter(item => done.has(item.vacancy_id) || SUBMITTED.has(item.status))
                .map(item => done.get(item.vacancy_id) || item);
            setStatus(`Se registraron ${data.count} postulación(es) simulada(s).`);
            markApplicationsCompleted();
            if (data.count > 0) {
                unlockFollowupLink();
            }
        } catch (error) {
            setStatus(error instanceof TypeError
                ? "No pudimos conectar con Profilia. Intenta de nuevo."
                : error.message, true);
        } finally {
            running = false;
            render();
        }
    }

    async function saveLetter(item, text) {
        const body = new FormData();
        body.append("cover_letter", text);
        const response = await fetch(page.dataset.letterUrl.replace("__vacancy__", encodeURIComponent(item.vacancy_id)), {
            method: "POST",
            body,
            headers: { "X-CSRFToken": csrfToken },
            credentials: "same-origin",
        });
        const data = await response.json().catch(() => ({ success: false, error: "Respuesta no válida." }));
        if (!response.ok || !data.success) {
            throw new Error(data.error || "No pudimos guardar tu carta.");
        }
        applications = applications.map(app => app.vacancy_id === item.vacancy_id ? data.application : app);
        openLetters.add(item.vacancy_id);
        render();
        setStatus(`Guardamos los cambios de tu carta para ${item.title}.`);
    }

    function initLetterEditor() {
        const modal = document.getElementById("letter-modal");
        const dialog = document.getElementById("letter-dialog");
        const textarea = document.getElementById("letter-textarea");
        const subtitle = document.getElementById("letter-modal-subtitle");
        const counter = document.getElementById("letter-counter");
        const errorLine = document.getElementById("letter-error");
        const saveButton = document.getElementById("save-letter-button");
        const closeButtons = [
            document.getElementById("close-letter-modal-button"),
            document.getElementById("cancel-letter-modal-button"),
        ];
        if (!modal || !dialog || !textarea || !saveButton) {
            return null;
        }

        const maxLength = Number(textarea.maxLength) || 4000;
        let current = null;
        let saving = false;
        let previousFocus = null;

        closeButtons.forEach(button => button?.addEventListener("click", () => close()));
        modal.addEventListener("click", event => {
            if (event.target === modal || event.target === modal.firstElementChild) {
                close();
            }
        });
        modal.addEventListener("keydown", event => {
            if (event.key === "Escape") {
                close();
            } else if (event.key === "Tab") {
                trapFocus(event);
            }
        });
        textarea.addEventListener("input", update);
        dialog.addEventListener("submit", async event => {
            event.preventDefault();
            const text = textarea.value.trim();
            if (!text) {
                errorLine.textContent = "La carta no puede quedar vacía.";
                textarea.focus();
                return;
            }
            saving = true;
            errorLine.textContent = "";
            update();
            try {
                await saveLetter(current, text);
                saving = false;
                close();
            } catch (error) {
                errorLine.textContent = error instanceof TypeError
                    ? "No pudimos conectar con Profilia. Intenta de nuevo."
                    : error.message;
            } finally {
                saving = false;
                update();
            }
        });

        function open(item) {
            current = item;
            previousFocus = document.activeElement;
            subtitle.textContent = `${item.title} · ${item.company}`;
            textarea.value = item.cover_letter || "";
            errorLine.textContent = "";
            update();
            modal.classList.remove("hidden");
            modal.setAttribute("aria-hidden", "false");
            textarea.focus();
            textarea.setSelectionRange(0, 0);
            textarea.scrollTop = 0;
        }

        function close() {
            if (saving || modal.classList.contains("hidden")) {
                return;
            }
            modal.classList.add("hidden");
            modal.setAttribute("aria-hidden", "true");
            current = null;
            // Tras guardar se vuelve a pintar la lista: el foco vuelve al botón de la misma carta.
            const target = previousFocus?.isConnected ? previousFocus
                : list.querySelector(`[data-edit-letter="${CSS.escape(previousFocus?.dataset?.editLetter || "")}"]`);
            target?.focus();
        }

        function update() {
            const length = textarea.value.length;
            counter.textContent = `${length} / ${maxLength} caracteres`;
            const unchanged = current && textarea.value.trim() === (current.cover_letter || "").trim();
            saveButton.disabled = saving || !textarea.value.trim() || unchanged;
            saveButton.querySelector("span").textContent = saving ? "Guardando..." : "Guardar carta";
            textarea.readOnly = saving;
        }

        function trapFocus(event) {
            const focusable = [...dialog.querySelectorAll("button, textarea")].filter(node => !node.disabled);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }

        return { open };
    }

    function pendingCount() {
        return applications.filter(item => item.status === "seleccionada").length;
    }

    function updateButton() {
        const pending = pendingCount();
        startButton.disabled = running || pending === 0;
        startButton.querySelector("span").textContent = running
            ? "Postulando..."
            : pending === 0 && applications.length ? "Sin postulaciones pendientes" : "Iniciar proceso automático";
    }

    function render() {
        list.replaceChildren(...applications.map(buildCard));
        emptyState.classList.toggle("hidden", applications.length > 0);
        updateButton();
    }

    function buildCard(item) {
        const status = STATUS[item.status] || STATUS.seleccionada;
        const card = element("article", "p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3 text-xs");

        const header = element("div", "flex items-start justify-between gap-3");
        const titleBox = element("div", "min-w-0");
        titleBox.append(
            element("p", "font-bold text-[#13223a] text-sm break-words", item.title),
            element("p", "text-slate-500", item.company),
        );
        const badges = element("div", "flex flex-wrap items-center justify-end gap-2 shrink-0");
        if (item.score > 0) {
            badges.append(element("span", "px-2.5 py-0.5 rounded-full border bg-white text-[#13223a] border-slate-200 text-[11px] font-black",
                `${item.score}% MATCH`));
        }
        badges.append(element("span", `px-2 py-0.5 rounded border text-[10px] font-bold ${status.classes}`, status.label));
        header.append(titleBox, badges);
        card.append(header);

        (item.warnings || []).forEach(text => card.append(
            element("p", "px-2.5 py-1.5 rounded-lg bg-amber-50 text-amber-800 border border-amber-200", text)));

        if (SUBMITTED.has(item.status)) {
            card.append(letterDetails(item), screeningDetails(item), element("p", "text-[11px] text-slate-500", footer(item)));
        }
        return card;
    }

    function letterDetails(item) {
        const details = element("details", "rounded-lg border border-slate-200 bg-white");
        details.open = openLetters.has(item.vacancy_id);
        details.addEventListener("toggle", () => {
            if (details.open) {
                openLetters.add(item.vacancy_id);
            } else {
                openLetters.delete(item.vacancy_id);
            }
        });
        details.append(element("summary", "px-3 py-2 min-h-[44px] flex items-center cursor-pointer font-semibold text-[#13223a]",
            "Ver carta de presentación"));
        details.append(element("p", "px-3 whitespace-pre-line leading-relaxed text-slate-700", item.cover_letter));
        if (editor) {
            const actions = element("div", "px-3 py-3 flex justify-end");
            const button = element("button", "min-h-[44px] px-4 rounded-xl bg-[#13223a] hover:bg-slate-800 text-white text-xs font-bold transition flex items-center gap-2");
            button.type = "button";
            button.dataset.editLetter = item.vacancy_id;
            button.setAttribute("aria-label", `Editar carta para ${item.title}`);
            const icon = element("i", "fa-solid fa-pen-to-square");
            icon.setAttribute("aria-hidden", "true");
            button.append(icon, element("span", "", "Editar carta"));
            button.addEventListener("click", () => editor.open(item));
            actions.append(button);
            details.append(actions);
        }
        return details;
    }

    function screeningDetails(item) {
        const details = element("details", "rounded-lg border border-slate-200 bg-white");
        details.append(element("summary", "px-3 py-2 min-h-[44px] flex items-center cursor-pointer font-semibold text-[#13223a]",
            `Ver respuestas de filtro (${item.screening.length})`));
        const answers = element("ul", "px-3 pb-3 space-y-2");
        item.screening.forEach(answer => {
            const row = element("li", "space-y-0.5");
            row.append(
                element("p", "font-semibold text-slate-700", answer.question),
                element("p", "text-slate-600", answer.answer),
                element("p", "text-[10px] text-slate-400", SCREENING_LABELS[answer.status] || ""),
            );
            answers.append(row);
        });
        details.append(answers);
        return details;
    }

    function footer(item) {
        const date = item.submitted_at ? new Date(item.submitted_at).toLocaleString("es-CO") : "";
        const origin = LETTER_ORIGINS[item.letter_source] || "Carta basada en tu perfil";
        return `${item.channel} · ${origin}${date ? ` · ${date}` : ""}`;
    }

    function setStatus(text, isError = false) {
        statusLine.textContent = text;
        statusLine.className = `text-xs ${isError ? "text-red-700" : "text-slate-600"}`;
    }
}

function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initApplications);
}
