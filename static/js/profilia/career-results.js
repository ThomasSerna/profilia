const careerResultsSection = document.getElementById("career-results-section");
const careerResultsTitle = document.getElementById("career-results-title");
const careerResults = document.getElementById("career-results");
const roleTemplate = document.getElementById("career-role-template");
const requirementTemplate = document.getElementById("career-requirement-template");
const chat = document.getElementById("profile-chat-messages");
const chatTemplate = document.getElementById("career-chat-template");
const clarificationForm = document.getElementById("career-clarification-form");
const clarificationFields = document.getElementById("career-clarification-fields");
const clarificationTemplate = document.getElementById("career-clarification-template");
const groups = {
    high: "Alta afinidad",
    medium: "Afinidad media",
    low: "Baja afinidad",
    pending: "Resultado pendiente",
};
const requirementLabels = {
    evidencia_en_perfil: "Con evidencia",
    cumple: "Compatible",
    incumple: "No cumple según la información disponible",
    sin_evidencia: "Sin evidencia suficiente",
};
let busy = false;

export function initCareerResults(onClarify, onRetry) {
    clarificationForm.addEventListener("change", updateClarificationControls);
    clarificationForm.addEventListener("submit", event => {
        event.preventDefault();

        if (busy) {
            return;
        }

        const clarifications = Object.create(null);

        for (const field of clarificationFields.children) {
            const answer = field.querySelector("[data-question-answer]").value;
            const detailInput = field.querySelector("[data-question-detail]");
            const detail = detailInput.value.trim();
            detailInput.setCustomValidity(answer === "yes" && !detail
                ? "Describe dónde y cómo has usado esta habilidad."
                : "");
            clarifications[field.dataset.skill] = { answer, detail: answer === "yes" ? detail : "" };
        }

        if (clarificationForm.reportValidity()) {
            onClarify(clarifications);
        }
    });

    clarificationForm.addEventListener("input", event => {
        if (event.target.matches("[data-question-detail]")) {
            event.target.setCustomValidity("");
        }
    });

    chat.addEventListener("click", event => {
        if (busy) {
            return;
        }

        const retryButton = event.target.closest("[data-retry-recommendation]");

        if (retryButton) {
            onRetry(retryButton.dataset.roleName);
        }

        if (event.target.closest("[data-complete-information]")) {
            document.getElementById("career-clarification-title").focus();
            clarificationForm.scrollIntoView({ block: "start" });
        }
    });
}

export function setCareerResultsBusy(value) {
    busy = value;
    careerResultsSection.setAttribute("aria-busy", String(value));
    chat.setAttribute("aria-busy", String(value));
    chat.querySelectorAll("button").forEach(button => { button.disabled = value; });
    clarificationForm.querySelector("button[type=submit]").disabled = value;
    updateClarificationControls();
}

export function renderAssessments(assessments, pendingQuestions = [], moveFocus = true) {
    careerResults.replaceChildren();
    chat.querySelectorAll("[data-career-message]").forEach(message => message.remove());

    for (const assessment of assessments) {
        const article = roleTemplate.content.firstElementChild.cloneNode(true);
        article.querySelector("[data-role-name]").textContent = assessment.role_name;
        article.querySelector("[data-role-group]").textContent = groups[assessment.group];
        article.querySelector("[data-role-score]").textContent =
            `Afinidad con los criterios: ${Math.round(assessment.score_min)}–` +
            `${Math.round(assessment.score_max)} / 100. Es un índice de ajuste, no una probabilidad de contratación.`;
        article.querySelector("[data-role-summary]").textContent = assessment.summary;

        const findings = article.querySelector("[data-role-findings]");

        for (const [label, items] of [
            ["Fortalezas", assessment.strengths],
            ["Brechas conocidas", assessment.gaps],
            ["Por confirmar", assessment.unknowns],
        ]) {
            if (items.length > 0) {
                const paragraph = document.createElement("p");
                paragraph.textContent = `${label}: ${items.join(" · ")}`;
                findings.append(paragraph);
            }
        }

        for (const requirement of assessment.requirements) {
            const row = renderRequirement(requirement);
            article.querySelector(requirement.category === "required"
                ? "[data-required-skills]"
                : "[data-preferred-skills]").append(row);
        }

        careerResults.append(article);
        renderChatMessage(assessment, pendingQuestions.length > 0);
    }

    renderClarificationQuestions(pendingQuestions);
    careerResultsSection.classList.toggle("hidden", assessments.length === 0);
    setCareerResultsBusy(busy);

    if (moveFocus && assessments.length > 0) {
        careerResultsTitle.focus({ preventScroll: true });
        careerResultsSection.scrollIntoView({ block: "start" });
    }

    chat.scrollTop = chat.scrollHeight;
}

function renderRequirement(requirement) {
    const row = requirementTemplate.content.firstElementChild.cloneNode(true);
    row.querySelector("[data-skill-name]").textContent = requirement.skill;
    const badge = row.querySelector("[data-skill-status]");
    const origin = requirement.source === "user_clarification"
        ? "declaración del usuario"
        : requirement.source === "rule" ? "regla del cargo" : "Kev";
    badge.textContent = `${requirementLabels[requirement.status]} · ${origin}`;
    badge.classList.add(...(requirement.status === "cumple" || requirement.status === "evidencia_en_perfil"
        ? ["bg-emerald-50", "text-emerald-800"]
        : requirement.status === "incumple"
            ? ["bg-rose-50", "text-rose-800"]
            : ["bg-slate-100", "text-slate-600"]));

    const evidenceText = row.querySelector("[data-skill-evidence]");
    evidenceText.textContent = requirement.evidence.map(item => {
        const source = item.source.startsWith("skills[")
            ? "Habilidades del CV"
            : item.source.startsWith("experience[") ? "Experiencia del CV" : "Declaración del usuario";
        return `${source}: ${item.value}`;
    }).join(" · ");
    evidenceText.hidden = requirement.evidence.length === 0;

    const probabilities = requirement.probabilities;
    const probabilitiesText = row.querySelector("[data-skill-probabilities]");
    probabilitiesText.hidden = !probabilities;

    if (probabilities) {
        probabilitiesText.textContent = probabilityText(probabilities) +
            ` Certeza reportada: ${Math.round(requirement.confidence * 100)}%.`;
    }

    const original = row.querySelector("[data-skill-original]");
    original.hidden = !requirement.kev_answer || (requirement.source === "kev" &&
        requirement.kev_answer.choice === requirement.status);

    if (!original.hidden) {
        original.textContent = `Lectura original de Kev: ${requirementLabels[requirement.kev_answer.choice]}. ` +
            probabilityText(requirement.kev_answer.probabilities);
    }

    const alternatives = row.querySelector("[data-skill-alternatives]");
    alternatives.hidden = !requirement.alternatives?.length;

    for (const alternative of requirement.alternatives || []) {
        alternatives.append(renderRequirement(alternative));
    }

    return row;
}

function probabilityText(probabilities) {
    return `Opciones de Kev: compatible ${Math.round(probabilities.cumple * 100)}% · ` +
        `no cumple ${Math.round(probabilities.incumple * 100)}% · ` +
        `sin evidencia ${Math.round(probabilities.sin_evidencia * 100)}%`;
}

function renderChatMessage(assessment, hasPendingQuestions) {
    const message = chatTemplate.content.firstElementChild.cloneNode(true);
    message.querySelector("[data-chat-role]").textContent = assessment.role_name;
    message.querySelector("[data-chat-group]").textContent = groups[assessment.group];
    message.querySelector("[data-chat-text]").textContent =
        assessment.recommendation?.text || assessment.summary;

    const actions = message.querySelector("[data-chat-actions]");
    actions.hidden = !assessment.recommendation?.actions.length;

    for (const action of assessment.recommendation?.actions || []) {
        const item = document.createElement("li");
        item.textContent = `${action.skill}: ${action.action} Para comprobar tu avance: ${action.evidence_of_progress}`;
        actions.append(item);
    }

    const recommendationPending = assessment.recommendation_status === "pending";
    const recommendationStatus = message.querySelector("[data-recommendation-status]");
    recommendationStatus.hidden = !recommendationPending;
    recommendationStatus.textContent = "La evaluación está guardada; la recomendación personalizada sigue pendiente. Puedes reintentarla.";
    const retry = message.querySelector("[data-retry-recommendation]");
    retry.hidden = !recommendationPending;
    retry.classList.toggle("hidden", !recommendationPending);
    retry.dataset.roleName = assessment.role_name;
    const complete = message.querySelector("[data-complete-information]");
    complete.hidden = assessment.group !== "pending" || !hasPendingQuestions;
    complete.classList.toggle("hidden", complete.hidden);
    chat.append(message);
}

function renderClarificationQuestions(questions) {
    clarificationFields.replaceChildren();
    clarificationForm.classList.toggle("hidden", questions.length === 0);

    questions.forEach((question, index) => {
        const field = clarificationTemplate.content.firstElementChild.cloneNode(true);
        field.dataset.skill = question.skill;
        field.querySelector("[data-question-label]").textContent = question.label;
        field.querySelector("[data-question-roles]").textContent = `Cargos: ${question.roles.join(" · ")}`;
        const answer = field.querySelector("[data-question-answer]");
        answer.id = `career-answer-${index}`;
        answer.value = question.answer || "";
        field.querySelector("[data-answer-label]").htmlFor = answer.id;
        const detail = field.querySelector("[data-question-detail]");
        detail.id = `career-detail-${index}`;
        detail.value = question.detail || "";
        field.querySelector("[data-detail-label]").htmlFor = detail.id;
        clarificationFields.append(field);
    });

    updateClarificationControls();
}

function updateClarificationControls() {
    for (const field of clarificationFields.children) {
        const answer = field.querySelector("[data-question-answer]");
        const detail = field.querySelector("[data-question-detail]");
        answer.disabled = busy;
        detail.required = answer.value === "yes";
        detail.disabled = busy || answer.value !== "yes";

        if (!detail.required) {
            detail.setCustomValidity("");
        }
    }
}
