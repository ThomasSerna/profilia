import {
    initCareerResults,
    renderAssessments,
    setCareerResultsBusy,
} from "./career-results.js";
import { hideNotifications, showErrorNotification } from "./notifications.js";

export function initRoleSelection(form, operations) {
    const roleModal = document.getElementById("role-modal");
    const roleDialog = document.getElementById("role-dialog");
    const closeRoleModalButton = document.getElementById("close-role-modal-button");
    const cancelRoleModalButton = document.getElementById("cancel-role-modal-button");
    const openRoleModalButton = document.getElementById("open-role-modal-button");
    const chooseRolesButton = document.getElementById("choose-roles-button");
    const recommendRolesButton = document.getElementById("recommend-roles-button");
    const roleSelectionSection = document.getElementById("role-selection-section");
    const roleSelectionTitle = document.getElementById("role-selection-title");
    const roleSelectionDescription = document.getElementById("role-selection-description");
    const roleCounter = document.getElementById("role-counter");
    const roleList = document.getElementById("role-list");
    const recommendationHint = document.getElementById("recommendation-hint");
    const recommendationHintText = document.getElementById("recommendation-hint-text");
    const confirmRolesButton = document.getElementById("confirm-roles-button");
    const selectedRolesInputs = document.getElementById("selected-roles-inputs");
    const roleCards = Array.from(document.querySelectorAll(".role-option"));

    let profileRevision = "";
    let selectedRoles = new Set();
    let confirmedRoles = [];
    let currentRoleMode = null;
    let suggestions = [];
    let previousFocus = null;

    initCareerResults(submitClarifications, retryRecommendation);

    openRoleModalButton.addEventListener("click", () => {
        if (!operations.isBusy()) {
            openRoleModal(false);
        }
    });
    closeRoleModalButton.addEventListener("click", () => closeRoleModal());
    cancelRoleModalButton.addEventListener("click", () => closeRoleModal());
    roleModal.addEventListener("click", event => {
        if (event.target === roleModal) {
            closeRoleModal();
        }
    });

    document.addEventListener("keydown", event => {
        if (roleModal.classList.contains("hidden")) {
            return;
        }

        if (event.key === "Escape") {
            closeRoleModal();
        }

        if (event.key === "Tab") {
            const controls = [...roleDialog.querySelectorAll(
                "button:not([disabled]), input:not([disabled]), select:not([disabled])"
            )].filter(control => control.getClientRects().length > 0);
            const first = controls[0];
            const last = controls[controls.length - 1];

            if (!first) {
                event.preventDefault();
                roleDialog.focus();
            } else if (event.shiftKey && (document.activeElement === first ||
                document.activeElement === roleDialog)) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && (document.activeElement === last ||
                document.activeElement === roleDialog)) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    chooseRolesButton.addEventListener("click", () => {
        if (operations.isBusy()) {
            return;
        }

        selectedRoles = new Set(confirmedRoles);
        currentRoleMode = "manual";
        setRoleModeButton(chooseRolesButton);
        showManualRoles();
    });

    recommendRolesButton.addEventListener("click", async () => {
        if (operations.isBusy() || !profileRevision) {
            return;
        }

        await postCareer(
            confirmRolesButton.dataset.explorationUrl,
            new FormData(),
            "Explorando cargos con tu perfil...",
            data => {
                suggestions = data.suggestions || [];
                selectedRoles = new Set();
                currentRoleMode = "recommended";
                setRoleModeButton(recommendRolesButton);
                showRecommendedRoles();
            }
        );
    });

    roleList.addEventListener("change", event => {
        const checkbox = event.target.closest(".role-checkbox");

        if (!checkbox || operations.isBusy()) {
            return;
        }

        if (checkbox.checked && selectedRoles.size < 3) {
            selectedRoles.add(checkbox.value);
        } else {
            selectedRoles.delete(checkbox.value);
        }

        updateRoleSelectionUI();
    });

    confirmRolesButton.addEventListener("click", async () => {
        if (selectedRoles.size === 0 || operations.isBusy()) {
            return;
        }

        const data = rolesFormData([...selectedRoles]);
        await postCareer(
            confirmRolesButton.dataset.assessmentUrl,
            data,
            "Evaluando los cargos seleccionados...",
            result => {
                applyAssessmentResult(result);
                closeRoleModal(true);
            }
        );
    });

    updateControls();

    return { setProfile, setBusy: updateControls, openRoleModal, invalidateProfile };

    function invalidateProfile() {
        profileRevision = "";
        confirmedRoles = [];
        selectedRoles = new Set();
        suggestions = [];
        currentRoleMode = null;
        roleSelectionSection.classList.add("hidden");
        recommendationHint.classList.add("hidden");
        clearRoleModeButtons();
        renderAssessments([], [], false);
        syncSelectedRolesInputs();
        document.getElementById("profile-status-badge").textContent = "Perfil actualizado: recarga";
        setOperationStatus("El perfil cambió. Recarga la página antes de continuar.");
        updateControls();
    }

    function setProfile(data, moveFocus = false) {
        profileRevision = data.profile_revision || "";
        suggestions = [];
        confirmedRoles = data.role_names || [];
        selectedRoles = new Set(confirmedRoles);
        currentRoleMode = confirmedRoles.length > 0 ? "manual" : null;
        clearRoleModeButtons();

        if (currentRoleMode) {
            setRoleModeButton(chooseRolesButton);
        }

        syncSelectedRolesInputs();
        renderAssessments(data.assessments || [], data.pending_questions || [], moveFocus);
        setOperationStatus("");
        updateControls();
    }

    function applyAssessmentResult(data) {
        profileRevision = data.profile_revision;
        confirmedRoles = data.role_names || data.roles.map(role => role.name);
        selectedRoles = new Set(confirmedRoles);
        suggestions = [];
        currentRoleMode = "manual";
        setRoleModeButton(chooseRolesButton);
        syncSelectedRolesInputs();
        renderAssessments(data.assessments, data.pending_questions || []);
        updateControls();
    }

    async function submitClarifications(clarifications) {
        const data = rolesFormData(confirmedRoles);
        data.append("clarifications", JSON.stringify(clarifications));
        await postCareer(
            confirmRolesButton.dataset.clarificationUrl,
            data,
            "Guardando tus declaraciones y revisando los cargos...",
            applyAssessmentResult
        );
    }

    async function retryRecommendation(roleName) {
        const data = new FormData();
        data.append("role", roleName);
        await postCareer(
            confirmRolesButton.dataset.retryUrl,
            data,
            "Preparando la recomendación personalizada...",
            applyAssessmentResult
        );
    }

    function rolesFormData(names) {
        const data = new FormData();
        names.forEach(name => data.append("roles", name));
        return data;
    }

    async function postCareer(url, data, loadingMessage, onSuccess) {
        if (operations.isBusy() || !profileRevision) {
            return;
        }

        const requestedRevision = profileRevision;
        data.append("profile_revision", requestedRevision);
        operations.setBusy(true);
        hideNotifications();
        setOperationStatus(loadingMessage);

        try {
            const response = await fetch(url, {
                method: "POST",
                mode: "same-origin",
                body: data,
                headers: {
                    "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value,
                },
            });

            if (response.redirected || response.status === 401 || response.status === 403) {
                throw new Error("Tu sesión venció o no permite esta operación. Vuelve a iniciar sesión.");
            }

            const result = await response.json().catch(() => ({}));

            if (requestedRevision !== profileRevision) {
                return;
            }

            if (!response.ok || !result.success) {
                if (response.status === 409) {
                    invalidateProfile();
                } else if (result.profile_revision) {
                    profileRevision = result.profile_revision;
                }

                throw new Error(result.error || "No se pudo completar la solicitud.");
            }

            profileRevision = result.profile_revision;
            onSuccess(result);
            setOperationStatus("");
        } catch (error) {
            showErrorNotification(error.message);
            setOperationStatus(error.message);
        } finally {
            operations.setBusy(false);
        }
    }

    function setOperationStatus(message) {
        document.getElementById("career-operation-status").textContent = message;
        document.getElementById("role-operation-status").textContent = message;
    }

    function openRoleModal(resetMode) {
        if (!profileRevision) {
            return;
        }

        previousFocus = document.activeElement;

        if (resetMode || !currentRoleMode) {
            currentRoleMode = null;
            roleSelectionSection.classList.add("hidden");
            recommendationHint.classList.add("hidden");
            clearRoleModeButtons();
        } else if (currentRoleMode === "manual") {
            showManualRoles();
        } else {
            showRecommendedRoles();
        }

        roleModal.classList.remove("hidden");
        roleModal.setAttribute("aria-hidden", "false");
        document.body.classList.add("overflow-hidden");

        if (operations.isBusy()) {
            roleDialog.focus();
        } else {
            chooseRolesButton.focus();
        }
    }

    function closeRoleModal(force = false) {
        if (operations.isBusy() && !force) {
            return;
        }

        roleModal.classList.add("hidden");
        roleModal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("overflow-hidden");
        previousFocus?.focus();
    }

    function setRoleModeButton(activeButton) {
        clearRoleModeButtons();
        activeButton.classList.remove("border-slate-200");
        activeButton.classList.add("border-[#02bc4d]", "bg-emerald-50");
    }

    function clearRoleModeButtons() {
        document.querySelectorAll(".role-mode-button").forEach(button => {
            button.classList.remove("border-[#02bc4d]", "bg-emerald-50");
            button.classList.add("border-slate-200");
        });
    }

    function showManualRoles() {
        roleSelectionSection.classList.remove("hidden");
        recommendationHint.classList.add("hidden");
        roleSelectionTitle.textContent = "Selecciona los cargos que te interesan";
        roleSelectionDescription.textContent = "Puedes seleccionar entre 1 y 3 cargos.";

        [...roleCards].sort((a, b) => Number(a.dataset.originalIndex) -
            Number(b.dataset.originalIndex)).forEach(card => {
            card.classList.remove("hidden");
            card.querySelector(".role-recommendation-badge").classList.add("hidden");
            card.querySelector("[data-role-suggestion]").classList.add("hidden");
            roleList.append(card);
        });

        updateRoleSelectionUI();
    }

    function showRecommendedRoles() {
        const usefulSuggestions = suggestions.filter(item => item.strengths.length > 0).slice(0, 3);
        roleSelectionSection.classList.remove("hidden");
        recommendationHint.classList.remove("hidden");
        roleSelectionTitle.textContent = "Opciones para explorar";
        roleSelectionDescription.textContent = usefulSuggestions.length > 0
            ? "Confirma entre 1 y 3 opciones para recibir orientación."
            : "No hay evidencia suficiente para sugerir cargos. Puedes elegirlos manualmente.";
        recommendationHintText.textContent = "Estas opciones se basan en la evidencia disponible. La información pendiente no significa falta de capacidad.";

        for (const card of roleCards) {
            card.classList.add("hidden");
        }

        for (const suggestion of usefulSuggestions) {
            const card = roleCards.find(item => item.dataset.roleName === suggestion.role_name);

            if (!card) {
                continue;
            }

            card.classList.remove("hidden");
            const badge = card.querySelector(".role-recommendation-badge");
            badge.textContent = suggestion.group === "pending" ? "Pendiente" : "Por explorar";
            badge.classList.remove("hidden");
            badge.classList.toggle("bg-emerald-100", suggestion.group !== "pending");
            badge.classList.toggle("text-emerald-700", suggestion.group !== "pending");
            badge.classList.toggle("bg-slate-100", suggestion.group === "pending");
            badge.classList.toggle("text-slate-600", suggestion.group === "pending");
            const detail = card.querySelector("[data-role-suggestion]");
            detail.classList.remove("hidden");
            detail.textContent =
                `Afinidad: ${Math.round(suggestion.score_min)}–${Math.round(suggestion.score_max)} / 100. ` +
                `Cobertura obligatoria confirmada: ${Math.round(suggestion.required_coverage * 100)}%. ` +
                `Fortalezas: ${suggestion.strengths.join(", ")}.` +
                (suggestion.unknowns.length > 0 ? ` Por confirmar: ${suggestion.unknowns.join(", ")}.` : "");
            roleList.append(card);
        }

        updateRoleSelectionUI();
    }

    function updateControls() {
        const busy = operations.isBusy();
        document.getElementById("profile-revision-input").value = profileRevision;
        openRoleModalButton.disabled = busy || !profileRevision;
        chooseRolesButton.disabled = busy || !profileRevision;
        recommendRolesButton.disabled = busy || !profileRevision;
        closeRoleModalButton.disabled = busy;
        cancelRoleModalButton.disabled = busy;
        roleDialog.setAttribute("aria-busy", String(busy));
        openRoleModalButton.className = "w-full py-2.5 px-4 rounded-xl bg-[#13223a] text-white font-bold text-xs transition-all flex items-center justify-center gap-2 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed";
        const label = openRoleModalButton.querySelector("span");
        label.textContent = !profileRevision
            ? "Procesa tu CV para continuar"
            : confirmedRoles.length > 0
                ? `${confirmedRoles.length} ${confirmedRoles.length === 1 ? "cargo seleccionado" : "cargos seleccionados"} · Cambiar`
                : "Seleccionar cargos y continuar";
        updateRoleSelectionUI();
        setCareerResultsBusy(busy);

        if (busy && !roleModal.classList.contains("hidden") && document.activeElement.disabled) {
            roleDialog.focus();
        }
    }

    function updateRoleSelectionUI() {
        const limitReached = selectedRoles.size >= 3;
        const busy = operations.isBusy();

        for (const card of roleCards) {
            const checkbox = card.querySelector(".role-checkbox");
            checkbox.checked = selectedRoles.has(checkbox.value);
            checkbox.disabled = busy || !profileRevision || (limitReached && !checkbox.checked);
            card.classList.toggle("border-slate-200", !checkbox.checked);
            card.classList.toggle("border-[#02bc4d]", checkbox.checked);
            card.classList.toggle("bg-emerald-50", checkbox.checked);
            card.classList.toggle("opacity-50", checkbox.disabled);
            card.classList.toggle("cursor-not-allowed", checkbox.disabled);
        }

        roleCounter.textContent = `${selectedRoles.size} / 3`;
        confirmRolesButton.disabled = busy || !profileRevision || selectedRoles.size === 0;
        confirmRolesButton.className = "px-5 py-2.5 rounded-xl bg-[#02bc4d] text-white text-xs font-bold flex items-center gap-2 transition disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed";
    }

    function syncSelectedRolesInputs() {
        selectedRolesInputs.replaceChildren();

        for (const name of confirmedRoles) {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "roles";
            input.value = name;
            selectedRolesInputs.append(input);
        }
    }
}
