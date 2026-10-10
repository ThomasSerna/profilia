const copFormatter = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
});

export function formatSalary(min, max) {
    const high = max ?? min;
    if (min == null && max == null) {
        return "Salario no publicado";
    }
    if (min != null && max != null && min !== max) {
        return `${copFormatter.format(min)} - ${copFormatter.format(max)}`;
    }
    return copFormatter.format(high);
}

export function scoreClasses(score) {
    if (score >= 80) {
        return "bg-emerald-100 text-[#02bc4d] border-emerald-200";
    }
    if (score >= 60) {
        return "bg-amber-100 text-amber-800 border-amber-200";
    }
    return "bg-slate-100 text-slate-600 border-slate-200";
}

export function initVacancies() {
    const page = document.getElementById("vacancy-page");
    const preferencesForm = document.getElementById("vacancy-preferences-form");
    const preferencesStatus = document.getElementById("preferences-status");
    const refreshButton = document.getElementById("refresh-vacancies-button");
    const status = document.getElementById("vacancy-status");
    const summary = document.getElementById("vacancy-summary");
    const list = document.getElementById("vacancy-list");
    const selectionCount = document.getElementById("vacancy-selection-count");
    const confirmButton = document.getElementById("confirm-vacancies-button");
    const confirmMessage = document.getElementById("vacancy-confirm-message");

    if (!page || !preferencesForm || !list || !confirmButton) {
        return;
    }

    const matchUrl = page.dataset.matchUrl;
    let selected = new Set();
    let titles = new Map();

    const savedElement = document.getElementById("saved-preferences");
    const hasPreferences = savedElement && Object.keys(JSON.parse(savedElement.textContent || "{}")).length > 0;

    preferencesForm.addEventListener("submit", event => {
        event.preventDefault();
        savePreferences();
    });

    refreshButton.addEventListener("click", () => search());

    confirmButton.addEventListener("click", () => {
        const names = [...selected].map(id => titles.get(id)).filter(Boolean);
        confirmMessage.textContent =
            `Seleccionaste ${names.length} vacante(s). El Agente de Postulación se conectará en el siguiente paso.`;
    });

    if (hasPreferences) {
        search();
    } else {
        setStatus("Guarda tus preferencias para ver tus coincidencias.");
    }

    async function savePreferences() {
        setPreferencesBusy(true);
        preferencesStatus.textContent = "Guardando preferencias...";
        preferencesStatus.className = "pt-3 text-xs text-slate-600";

        try {
            const response = await postForm(preferencesForm.action, new FormData(preferencesForm));
            const data = await response.json().catch(() => ({ success: false, error: "Respuesta no válida." }));
            if (!response.ok || !data.success) {
                throw new Error(data.error || "No pudimos guardar tus preferencias.");
            }
            preferencesStatus.textContent = "Preferencias guardadas.";
            refreshButton.disabled = false;
            search();
        } catch (error) {
            preferencesStatus.textContent = error.message;
            preferencesStatus.className = "pt-3 text-xs text-red-700";
        } finally {
            setPreferencesBusy(false);
        }
    }

    async function search() {
        setStatus("Calculando coincidencias...");
        confirmMessage.textContent = "";
        refreshButton.disabled = true;

        try {
            const response = await postForm(matchUrl, new FormData(preferencesForm));
            const data = await response.json().catch(() => ({ success: false, error: "Respuesta no válida." }));

            if (!response.ok || !data.success) {
                throw new Error(data.error || "No pudimos calcular tus coincidencias.");
            }

            selected = new Set();
            titles = new Map(data.matches.map(match => [match.vacancy_id, match.title]));
            renderMatches(data.matches);
            setStatus("");
            summary.textContent = data.count
                ? `Encontramos ${data.count} vacantes ordenadas por coincidencia con tu perfil.`
                : "";
        } catch (error) {
            setStatus(error.message, true);
        } finally {
            refreshButton.disabled = false;
        }
    }

    function postForm(url, formData) {
        return fetch(url, {
            method: "POST",
            body: formData,
            headers: { "X-CSRFToken": preferencesForm.querySelector("[name=csrfmiddlewaretoken]").value },
            credentials: "same-origin",
        });
    }

    function renderMatches(matches) {
        list.replaceChildren();
        updateSelection();

        if (!matches.length) {
            list.append(element("p", "text-xs text-slate-500", "No hay vacantes para mostrar."));
            return;
        }

        matches.forEach(match => list.append(buildCard(match)));
    }

    function buildCard(match) {
        const card = element("article", "p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3 text-xs");

        const header = element("div", "flex items-start justify-between gap-3");
        const titleBox = element("div", "min-w-0");
        titleBox.append(
            element("p", "font-bold text-[#13223a] text-sm break-words", match.title),
            element("p", "text-slate-500", match.company),
        );
        const badge = element(
            "span",
            `shrink-0 px-2.5 py-0.5 rounded-full border text-[11px] font-black ${scoreClasses(match.score)}`,
            `${match.score}% MATCH`,
        );
        header.append(titleBox, badge);

        const location = match.modality === "remoto"
            ? "Remoto"
            : `${match.modality[0].toUpperCase()}${match.modality.slice(1)} · ${match.city || "Ubicación no publicada"}`;
        const meta = element(
            "p",
            "text-slate-600",
            `${location} · ${formatSalary(match.salary_min, match.salary_max)}`,
        );

        const evidence = element("div", "space-y-2");
        if (match.matched_skills.length) {
            evidence.append(chipGroup("Coincidencias CV:", match.matched_skills,
                "bg-emerald-50 text-[#02bc4d] border-emerald-200/60"));
        }
        if (match.missing_required.length) {
            evidence.append(chipGroup("Te faltan:", match.missing_required,
                "bg-red-50 text-red-700 border-red-200"));
        }

        const reasons = element("p", "text-slate-600 leading-relaxed", match.reasons.join(" "));

        const footer = element("div", "flex flex-wrap items-center justify-between gap-2 pt-1");
        const label = element("label", "flex items-center gap-2 cursor-pointer font-semibold text-[#13223a]");
        const checkbox = element("input", "w-4 h-4 accent-[#02bc4d]");
        checkbox.type = "checkbox";
        checkbox.value = match.vacancy_id;
        checkbox.addEventListener("change", () => {
            if (checkbox.checked) {
                selected.add(match.vacancy_id);
            } else {
                selected.delete(match.vacancy_id);
            }
            updateSelection();
        });
        label.append(checkbox, document.createTextNode("Seleccionar para postular"));
        footer.append(label);

        if (!match.meets_preferences) {
            footer.append(element(
                "span",
                "text-[10px] px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-semibold",
                "Fuera de tus preferencias",
            ));
        }

        card.append(header, meta, evidence, reasons, footer);
        return card;
    }

    function chipGroup(label, items, classes) {
        const row = element("div", "flex flex-wrap items-center gap-1.5");
        row.append(element("span", "text-slate-400 font-medium mr-1", label));
        items.forEach(item => row.append(element("span", `px-2 py-0.5 rounded-md border font-semibold ${classes}`, item)));
        return row;
    }

    function updateSelection() {
        const count = selected.size;
        selectionCount.textContent = count
            ? `${count} vacante(s) seleccionada(s).`
            : "Ninguna vacante seleccionada.";
        confirmButton.disabled = count === 0;
    }

    function setStatus(text, isError = false) {
        status.textContent = text;
        status.className = `text-xs ${isError ? "text-red-700" : "text-slate-600"}`;
    }

    function setPreferencesBusy(value) {
        preferencesForm.querySelector("button[type=submit]").disabled = value;
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
    document.addEventListener("DOMContentLoaded", initVacancies);
}
