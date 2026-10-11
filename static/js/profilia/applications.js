const STATUS = {
    seleccionada: {
        label: "Pendiente",
        classes: "bg-slate-200 text-slate-600 border-slate-300",
    },
    postulada: {
        label: "Postulado ✓",
        classes: "bg-emerald-100 text-[#02bc4d] border-emerald-200",
    },
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
    const consoleBox = document.getElementById("application-console");
    const savedElement = document.getElementById("saved-applications");

    if (!page || !form || !startButton || !list || !consoleBox) {
        return;
    }

    let applications = JSON.parse(savedElement?.textContent || "[]");
    let running = false;
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

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
        consoleBox.replaceChildren(logLine("agent", "[AGENTE] Iniciando automatización de postulación con LangGraph Agent..."));
        updateButton();

        try {
            const response = await fetch(page.dataset.runUrl, {
                method: "POST",
                body: new FormData(form),
                headers: { "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value },
                credentials: "same-origin",
            });
            const data = await response.json().catch(() => ({ success: false, error: "Respuesta no válida." }));

            if (!response.ok || !data.success) {
                throw new Error(data.error || "No pudimos preparar tus postulaciones.");
            }

            await replay(data.events.slice(1));
            const done = new Map(data.applications.map(item => [item.vacancy_id, item]));
            applications = applications
                .filter(item => done.has(item.vacancy_id) || item.status === "postulada")
                .map(item => done.get(item.vacancy_id) || item);
            setStatus(`Se registraron ${data.count} postulación(es) simulada(s).`);
        } catch (error) {
            consoleBox.append(logLine("error", `[ERROR] ${error.message}`));
            setStatus(error instanceof TypeError
                ? "No pudimos conectar con Profilia. Intenta de nuevo."
                : error.message, true);
        } finally {
            running = false;
            render();
        }
    }

    async function replay(events) {
        for (const item of events) {
            consoleBox.append(logLine(item.level, item.message));
            consoleBox.scrollTop = consoleBox.scrollHeight;
            if (!reducedMotion) {
                await new Promise(resolve => setTimeout(resolve, 350));
            }
        }
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

        if (item.status === "postulada") {
            card.append(letterDetails(item), screeningDetails(item), element("p", "text-[11px] text-slate-500", footer(item)));
        }
        return card;
    }

    function letterDetails(item) {
        const details = element("details", "rounded-lg border border-slate-200 bg-white");
        details.append(element("summary", "px-3 py-2 min-h-[44px] flex items-center cursor-pointer font-semibold text-[#13223a]",
            "Ver carta de presentación"));
        details.append(element("p", "px-3 pb-3 whitespace-pre-line leading-relaxed text-slate-700", item.cover_letter));
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
        const origin = item.letter_source === "groq" ? "Carta redactada por Profilia" : "Carta basada en tu perfil";
        return `${item.channel} · ${origin}${date ? ` · ${date}` : ""}`;
    }

    function logLine(level, text) {
        return element("p", EVENT_CLASSES[level] || EVENT_CLASSES.step, text);
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
