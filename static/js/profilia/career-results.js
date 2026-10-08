const chat = document.getElementById("profile-chat-messages");
const chatTemplate = document.getElementById("career-chat-template");
const questionTemplate = document.getElementById("career-question-template");
const chatForm = document.getElementById("career-chat-form");
const detailInput = document.getElementById("career-chat-input");
const sendButton = document.getElementById("career-chat-send");
const groups = {
    high: "Encontramos fortalezas relacionadas con este cargo.",
    medium: "Hay fortalezas que puedes desarrollar para acercarte a este cargo.",
    low: "Podemos ayudarte a preparar tus próximos pasos hacia este cargo.",
    pending: "Necesitamos conocer un poco más de ti para orientar este cargo.",
};
let busy = false;
let questions = [];
let answers = [];
let currentQuestion = null;
let selectedAnswer = "";
let reviewQueue = null;
let activeRoles = "";
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

        if (event.target.closest("[data-review-unknown]")) {
            reviewQueue = questions.filter(question => question.answer === "unknown")
                .map(question => question.skill);
            renderNextQuestion(true);
        }
    });
}

export function setCareerResultsBusy(value) {
    busy = value;
    chat.setAttribute("aria-busy", String(value));
    chat.querySelectorAll("button").forEach(button => { button.disabled = value; });
    updateQuestionControls();
}

export function renderAssessments(assessments, pendingQuestions = [], answeredQuestions = [], moveFocus = true) {
    questions = pendingQuestions;
    answers = answeredQuestions;
    chat.querySelectorAll("[data-career-message]").forEach(message => message.remove());

    const roleNames = assessments.map(assessment => assessment.role_name).sort().join("\n");

    if (roleNames !== activeRoles || assessments.length === 0) {
        reviewQueue = null;
    }
    activeRoles = roleNames;

    for (const assessment of assessments) {
        renderRecommendation(assessment);
    }

    for (const answer of answers) {
        renderSavedAnswer(answer);
    }

    renderNextQuestion(moveFocus && assessments.length > 0);
    setCareerResultsBusy(busy);
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
        if (reviewQueue) {
            reviewQueue = reviewQueue.filter(item => item !== skill);
            if (reviewQueue.length === 0) {
                reviewQueue = null;
            }
        }
        selectedAnswer = "";
        detailInput.value = "";
        detailInput.setCustomValidity("");
        renderNextQuestion(true);
    }
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
            ? "La información que falta en tu hoja de vida no significa que no tengas la capacidad. Conversemos sobre ella."
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

function renderNextQuestion(moveFocus) {
    chat.querySelectorAll("[data-career-question], [data-career-finish]")
        .forEach(message => message.remove());
    const answeredSkills = new Set(answers.map(answer => answer.skill));
    const next = reviewQueue
        ? reviewQueue.map(skill => questions.find(question => question.skill === skill)).find(Boolean)
        : questions.find(question => !answeredSkills.has(question.skill) && !question.answer);

    if (next?.skill !== currentQuestion?.skill || !next) {
        selectedAnswer = "";
        detailInput.value = "";
        detailInput.setCustomValidity("");
    }
    currentQuestion = next || null;

    if (next) {
        const message = questionTemplate.content.firstElementChild.cloneNode(true);
        message.dataset.skill = next.skill;
        message.querySelector("[data-question-title]").textContent = `¿Conoces o has utilizado ${next.label}?`;
        message.querySelector("[data-question-roles]").textContent = `Nos ayudará a orientar: ${next.roles.join(" · ")}.`;
        chat.append(message);
    } else if (chat.querySelector("[data-career-message]")) {
        renderConversationEnd();
    }

    updateQuestionControls();
    scrollChatToEnd();

    if (moveFocus) {
        focusCareerQuestion();
    }
}

function renderConversationEnd() {
    const message = document.createElement("div");
    message.dataset.careerMessage = "";
    message.dataset.careerFinish = "";
    message.className = "max-w-[95%] rounded-2xl rounded-tl-none border border-slate-200 bg-slate-100 p-3.5 space-y-2";
    const text = document.createElement("p");
    text.tabIndex = -1;
    const uncertain = questions.some(question => question.answer === "unknown");
    text.textContent = !chat.querySelector("[data-chat-role]")
        ? "Conservamos tus respuestas. Elige los cargos que te interesan para actualizar tu orientación."
        : uncertain
        ? "Guardamos tus respuestas. Algunas dudas todavía impiden completar la orientación. Puedes revisarlas cuando estés listo; tener dudas no significa que te falte capacidad."
        : `${answers.length ? "Guardamos tus respuestas." : "Tu orientación está lista."} Puedes consultar la orientación de tus cargos en este chat o elegir otros cargos para continuar.`;
    message.append(text);

    if (uncertain) {
        const review = document.createElement("button");
        review.type = "button";
        review.dataset.reviewUnknown = "";
        review.textContent = "Revisar mis dudas";
        review.className = "min-h-[44px] font-bold text-[#13223a] underline disabled:opacity-50";
        review.disabled = busy;
        message.append(review);
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
