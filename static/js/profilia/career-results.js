const chat = document.getElementById("profile-chat-messages");
const chatTemplate = document.getElementById("career-chat-template");
const noticeTemplate = document.getElementById("career-notice-template");
const questionTemplate = document.getElementById("career-question-template");
const chatForm = document.getElementById("career-chat-form");
const detailInput = document.getElementById("career-chat-input");
const sendButton = document.getElementById("career-chat-send");
const groups = {
    high: "Encontramos fortalezas relacionadas con este cargo.",
    medium: "Hay fortalezas que puedes desarrollar para acercarte a este cargo.",
    low: "Podemos ayudarte a preparar tus próximos pasos hacia este cargo.",
    pending: "Todavía no tenemos información suficiente para orientar este cargo.",
};
let busy = false;
let assessments = [];
let questions = [];
let answers = [];
let currentQuestion = null;
let selectedAnswer = "";
let submitClarification;

export function initCareerResults(onClarify, onRetry) {
    submitClarification = onClarify;
    document.fonts.ready.then(scrollChatToEnd);
    chatForm.addEventListener("submit", async event => {
        event.preventDefault();

        if (busy || !currentQuestion || selectedAnswer !== "yes") {
            return;
        }

        const detail = detailInput.value.trim();
        detailInput.setCustomValidity(!detail
            ? "Cuéntanos dónde y cómo conoces o has utilizado esta habilidad."
            : detail.length > 1000 ? "Puedes escribir hasta 1000 caracteres." : "");

        if (chatForm.reportValidity()) {
            await saveAnswer("yes", detail);
        }
    });
    detailInput.addEventListener("input", () => detailInput.setCustomValidity(""));
    chat.addEventListener("click", async event => {
        if (busy) {
            return;
        }

        const answerButton = event.target.closest("[data-question-answer]");

        if (answerButton && currentQuestion) {
            if (answerButton.dataset.questionAnswer === "yes") {
                selectedAnswer = "yes";
                updateQuestionControls();
                detailInput.focus();
            } else {
                await saveAnswer(answerButton.dataset.questionAnswer, "");
            }
            return;
        }

        const retryButton = event.target.closest("[data-retry-recommendation]");

        if (retryButton) {
            await onRetry(retryButton.dataset.roleName);
        }
    });
}

export function setCareerResultsBusy(value) {
    busy = value;
    chat.setAttribute("aria-busy", String(value));
    chat.querySelectorAll("button").forEach(button => { button.disabled = value; });
    updateQuestionControls();
}

export function renderAssessments(roleAssessments, pendingQuestions = [], answeredQuestions = [], moveFocus = true) {
    assessments = roleAssessments;
    questions = pendingQuestions;
    answers = answeredQuestions;
    renderConversation(moveFocus && assessments.length > 0);
}

export function focusCareerQuestion() {
    const message = chat.querySelector("[data-career-question]") || chat.querySelector("[data-career-finish]");
    const target = message?.querySelector("[tabindex]") || chat.querySelector("[data-chat-role]");
    target?.focus({ preventScroll: true });
    requestAnimationFrame(() => (message || target)?.scrollIntoView({ block: "nearest" }));
}

async function saveAnswer(answer, detail) {
    if (busy || !currentQuestion) {
        return;
    }

    const skill = currentQuestion.skill;
    const saved = await submitClarification({ [skill]: { answer, detail } });
    const recorded = answers.some(item => item.skill === skill && item.answer === answer && item.detail === detail);

    if (saved || recorded) {
        selectedAnswer = "";
        detailInput.value = "";
        detailInput.setCustomValidity("");
        renderConversation(true);
    }
}

// The chat is rebuilt from the saved state in conversation order: a notice, each question followed by
// its answer, then the next question or, once nothing is left to ask, the final orientation.
function renderConversation(moveFocus) {
    chat.querySelectorAll("[data-career-message]").forEach(message => message.remove());
    const answeredSkills = new Set(answers.map(answer => answer.skill));
    // An "unknown" answer is final for the conversation; it is not asked again.
    const next = questions.find(question => !answeredSkills.has(question.skill) && !question.answer);

    if (next?.skill !== currentQuestion?.skill || !next) {
        selectedAnswer = "";
        detailInput.value = "";
        detailInput.setCustomValidity("");
    }
    currentQuestion = next || null;

    if (assessments.length > 0 && (answers.length > 0 || next)) {
        renderNotice("Antes de darte tu orientación, queremos confirmar algunas habilidades que no encontramos en tu perfil.");
    }

    for (const answer of answers) {
        renderQuestion(answer, false);
        renderSavedAnswer(answer);
    }

    if (next) {
        renderQuestion(next, true);
    } else if (assessments.length > 0) {
        renderNotice(answers.length
            ? "Gracias por tus respuestas. Esta es la orientación que Profilia preparó para tus cargos."
            : "Esta es la orientación que Profilia preparó para tus cargos.", true);
        assessments.forEach(renderRecommendation);
    } else if (answers.length > 0) {
        renderNotice("Conservamos tus respuestas. Elige los cargos que te interesan para actualizar tu orientación.", true);
    }

    setCareerResultsBusy(busy);
    scrollChatToEnd();

    if (moveFocus) {
        focusCareerQuestion();
    }
}

function renderNotice(text, finish = false) {
    const message = noticeTemplate.content.firstElementChild.cloneNode(true);
    message.querySelector("[data-notice-text]").textContent = text;

    if (finish) {
        message.dataset.careerFinish = "";
    }

    chat.append(message);
}

function renderQuestion(question, active) {
    const message = questionTemplate.content.firstElementChild.cloneNode(true);
    message.dataset.skill = question.skill;
    const title = message.querySelector("[data-question-title]");
    title.textContent = `¿Conoces o has utilizado ${question.label}?`;
    message.querySelector("[data-question-roles]").textContent = `Nos ayudará a orientar: ${question.roles.join(" · ")}.`;

    if (!active) {
        // Questions already answered stay in the conversation as plain text, without answer controls.
        delete message.dataset.careerQuestion;
        message.dataset.careerAskedQuestion = "";
        title.removeAttribute("tabindex");
        message.querySelector("[role=group]").remove();
        message.querySelector("[data-question-context]").remove();
    }

    chat.append(message);
}

function renderRecommendation(assessment) {
    const message = chatTemplate.content.firstElementChild.cloneNode(true);
    message.querySelector("[data-chat-role]").textContent = assessment.role_name;
    const group = message.querySelector("[data-chat-group]");
    group.textContent = groups[assessment.group] || groups.pending;
    group.hidden = Boolean(assessment.summary && !assessment.recommendation);
    const findings = message.querySelector("[data-chat-findings]");

    for (const [label, items, showWithSummary] of [
        ["Fortalezas que encontramos", assessment.strengths, assessment.group === "pending"],
        ["Habilidades por desarrollar según lo que compartiste", assessment.gaps, ["high", "pending"].includes(assessment.group)],
        ["Información por confirmar", assessment.unknowns, assessment.group === "high"],
    ]) {
        if (items?.length > 0 && (assessment.recommendation || !assessment.summary || showWithSummary)) {
            const paragraph = document.createElement("p");
            paragraph.textContent = `${label}: ${items.join(" · ")}.`;
            findings.append(paragraph);
        }
    }

    if (assessment.recommendation && assessment.requirements?.some(requirement =>
        requirement.source === "user_clarification" || requirement.alternatives?.some(alternative =>
            alternative.source === "user_clarification"))) {
        const note = document.createElement("p");
        note.textContent = "Esta orientación también tiene en cuenta tus respuestas; no confirma por sí sola tus conocimientos.";
        findings.append(note);
    }

    message.querySelector("[data-chat-text]").textContent = assessment.recommendation?.text || assessment.summary ||
        (assessment.group === "pending"
            ? "La información que falta en tu perfil no significa que no tengas la capacidad."
            : "Profilia te orienta con la información que compartiste. Estos resultados no garantizan una contratación.");

    const actions = message.querySelector("[data-chat-actions]");
    actions.hidden = !assessment.recommendation?.actions?.length;

    for (const action of assessment.recommendation?.actions || []) {
        const item = document.createElement("li");
        item.textContent = `${action.skill}: ${action.action} Para reconocer tu avance: ${action.evidence_of_progress}`;
        actions.append(item);
    }

    const recommendationPending = assessment.recommendation_status === "pending";
    const recommendationStatus = message.querySelector("[data-recommendation-status]");
    recommendationStatus.hidden = !recommendationPending;
    recommendationStatus.textContent = "Tu evaluación está guardada. Aún falta preparar la recomendación; puedes volver a intentarlo.";
    const retry = message.querySelector("[data-retry-recommendation]");
    retry.hidden = !recommendationPending;
    retry.classList.toggle("hidden", !recommendationPending);
    retry.dataset.roleName = assessment.role_name;
    chat.append(message);
}

function renderSavedAnswer(answer) {
    const message = document.createElement("div");
    message.dataset.careerMessage = "";
    message.dataset.careerAnswer = "";
    message.dataset.skill = answer.skill;
    message.className = "ml-auto max-w-[88%] rounded-2xl rounded-tr-none border border-emerald-200 bg-emerald-50 p-3.5 space-y-1 break-words";
    const text = document.createElement("p");
    text.className = "font-semibold text-[#13223a]";
    text.textContent = answer.answer === "yes"
        ? `Sí, conozco o he utilizado ${answer.label}.`
        : answer.answer === "no" ? `No conozco ni he utilizado ${answer.label}.`
            : `No estoy seguro sobre ${answer.label}.`;
    message.append(text);

    if (answer.answer === "yes" && answer.detail) {
        const detail = document.createElement("p");
        detail.className = "whitespace-pre-line leading-relaxed";
        detail.textContent = answer.detail;
        message.append(detail);
    }

    chat.append(message);
}

function scrollChatToEnd() {
    requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });
}

function updateQuestionControls() {
    const needsDetail = Boolean(currentQuestion && selectedAnswer === "yes");
    detailInput.disabled = busy || !needsDetail;
    detailInput.required = needsDetail;
    sendButton.disabled = busy || !needsDetail;
    detailInput.placeholder = needsDetail
        ? "Cuéntame dónde y cómo la conoces o has utilizado"
        : currentQuestion ? "Elige Sí, No o No estoy seguro en el chat"
            : assessments.length > 0 ? "Tu orientación está lista. Puedes cambiar tus cargos para continuar"
                : "Las preguntas aparecerán aquí en el chat";
    const yes = chat.querySelector('[data-question-answer="yes"]');
    yes?.setAttribute("aria-pressed", String(needsDetail));
    yes?.classList.toggle("border-[#02bc4d]", needsDetail);
    const context = chat.querySelector("[data-question-context]");

    if (context) {
        context.hidden = !needsDetail;
    }

    if (!needsDetail) {
        detailInput.setCustomValidity("");
    }
}
