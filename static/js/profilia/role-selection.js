import { renderAssessments } from "./career-results.js";
import { hideNotifications, showErrorNotification } from "./notifications.js";
import { calculateRoleScore } from "./role-recommendations.js";

export function initRoleSelection(form) {
    const roleModal = document.getElementById("role-modal");
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
    const confirmRolesButton = document.getElementById("confirm-roles-button");
    const selectedRolesInputs = document.getElementById("selected-roles-inputs");
    const roleCards = Array.from(document.querySelectorAll(".role-option"));

    let processedProfile = null;
    let selectedRoles = new Set();
    let currentRoleMode = null;

    openRoleModalButton?.addEventListener("click", () => openRoleModal(false));
    closeRoleModalButton?.addEventListener("click", closeRoleModal);
    cancelRoleModalButton?.addEventListener("click", closeRoleModal);

    roleModal?.addEventListener("click", event => {
        if (event.target === roleModal) {
            closeRoleModal();
        }
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && roleModal && !roleModal.classList.contains("hidden")) {
            closeRoleModal();
        }
    });

    chooseRolesButton?.addEventListener("click", () => {
        currentRoleMode = "manual";
        setRoleModeButton(chooseRolesButton);
        showManualRoles();
    });

    recommendRolesButton?.addEventListener("click", () => {
        currentRoleMode = "recommended";
        setRoleModeButton(recommendRolesButton);
        showRecommendedRoles();
    });

    roleList?.addEventListener("change", event => {
        const checkbox = event.target.closest(".role-checkbox");

        if (!checkbox) {
            return;
        }

        if (checkbox.checked) {
            if (selectedRoles.size >= 3) {
                checkbox.checked = false;
                return;
            }

            selectedRoles.add(checkbox.value);
        } else {
            selectedRoles.delete(checkbox.value);
        }

        updateRoleSelectionUI();
    });

    confirmRolesButton?.addEventListener("click", async () => {
        if (selectedRoles.size === 0) {
            return;
        }

        confirmRolesButton.disabled = true;
        hideNotifications();

        try {
            const formData = new FormData();

            for (const name of selectedRoles) {
                formData.append("roles", name);
            }

            const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
            const response = await fetch(confirmRolesButton.dataset.assessmentUrl, {
                method: "POST",
                mode: "same-origin",
                body: formData,
                headers: { "X-CSRFToken": csrfToken },
            });

            if (response.redirected) {
                throw new Error("Vuelve a iniciar sesión para continuar.");
            }

            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                throw new Error(data.error || "No se pudo validar la selección.");
            }

            selectedRoles = new Set(data.roles.map(role => role.name));
            console.log("Selección validada por Django:", data);

            updateRoleSelectionUI();
            syncSelectedRolesInputs();
            closeRoleModal();
            updateRoleFlowButton();
            renderAssessments(data.assessments);
        } catch (error) {
            showErrorNotification(error.message);
        } finally {
            updateConfirmRolesButton();
        }
    });

    return { setProfile, restoreSelection, openRoleModal };

    function setProfile(profile) {
        processedProfile = profile;
        resetRoleSelection();
        enableRoleFlowButton();
    }

    function restoreSelection(roleNames) {
        selectedRoles = new Set(roleNames);
        currentRoleMode = "manual";
        setRoleModeButton(chooseRolesButton);
        updateRoleSelectionUI();
        syncSelectedRolesInputs();
        updateRoleFlowButton();
    }

    function openRoleModal(resetMode) {
        if (!roleModal) {
            return;
        }

        if (resetMode) {
            currentRoleMode = null;
            roleSelectionSection.classList.add("hidden");
            recommendationHint.classList.add("hidden");
            clearRoleModeButtons();
        } else if (currentRoleMode === "manual") {
            showManualRoles();
        } else if (currentRoleMode === "recommended") {
            showRecommendedRoles();
        }

        roleModal.classList.remove("hidden");
        document.body.classList.add("overflow-hidden");
    }

    function closeRoleModal() {
        if (!roleModal) {
            return;
        }

        roleModal.classList.add("hidden");
        document.body.classList.remove("overflow-hidden");
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
        roleSelectionTitle.textContent = "Selecciona los roles que te interesan";
        roleSelectionDescription.textContent = "Puedes seleccionar hasta 3 roles.";

        const orderedCards = [...roleCards].sort(
            (a, b) => Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex)
        );

        orderedCards.forEach(card => {
            card.classList.remove("hidden");
            card.querySelector(".role-recommendation-badge")?.classList.add("hidden");
            roleList.appendChild(card);
        });

        updateRoleSelectionUI();
    }

    function showRecommendedRoles() {
        roleSelectionSection.classList.remove("hidden");
        recommendationHint.classList.remove("hidden");
        roleSelectionTitle.textContent = "Roles recomendados para tu perfil";
        roleSelectionDescription.textContent = "Selecciona hasta 3 de los roles sugeridos.";

        const scoredCards = roleCards
            .map(card => ({ card, score: calculateRoleScore(card.dataset, processedProfile) }))
            .sort((a, b) => b.score - a.score ||
                Number(a.card.dataset.originalIndex) - Number(b.card.dataset.originalIndex));

        scoredCards.forEach(({ card }, index) => {
            card.classList.toggle("hidden", index >= 5);
            card.querySelector(".role-recommendation-badge")?.classList.toggle("hidden", index >= 5);
            roleList.appendChild(card);
        });

        if (!scoredCards.some(item => item.score > 0)) {
            roleSelectionDescription.textContent =
                "No encontramos coincidencias muy claras. Estas son algunas opciones que puedes explorar.";
        }

        updateRoleSelectionUI();
    }

    function updateRoleSelectionUI() {
        const limitReached = selectedRoles.size >= 3;

        roleCards.forEach(card => {
            const checkbox = card.querySelector(".role-checkbox");

            if (!checkbox) {
                return;
            }

            checkbox.checked = selectedRoles.has(checkbox.value);
            checkbox.disabled = limitReached && !checkbox.checked;
            card.classList.toggle("border-slate-200", !checkbox.checked);
            card.classList.toggle("border-[#02bc4d]", checkbox.checked);
            card.classList.toggle("bg-emerald-50", checkbox.checked);
            card.classList.toggle("opacity-50", checkbox.disabled);
            card.classList.toggle("cursor-not-allowed", checkbox.disabled);
        });

        if (roleCounter) {
            roleCounter.textContent = `${selectedRoles.size} / 3`;
        }

        updateConfirmRolesButton();
    }

    function updateConfirmRolesButton() {
        if (!confirmRolesButton) {
            return;
        }

        confirmRolesButton.disabled = selectedRoles.size === 0;

        if (confirmRolesButton.disabled) {
            confirmRolesButton.className =
                "px-5 py-2.5 rounded-xl bg-slate-200 text-slate-400 " +
                "text-xs font-bold flex items-center gap-2 cursor-not-allowed transition";
            return;
        }

        confirmRolesButton.className =
            "px-5 py-2.5 rounded-xl " +
            "bg-[#02bc4d] hover:bg-[#00a943] " +
            "text-white text-xs font-bold flex items-center gap-2 " +
            "cursor-pointer transition shadow-sm shadow-[#02bc4d]/20";
    }

    function syncSelectedRolesInputs() {
        if (!selectedRolesInputs) {
            return;
        }

        selectedRolesInputs.innerHTML = "";

        selectedRoles.forEach(roleName => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "roles";
            input.value = roleName;
            selectedRolesInputs.appendChild(input);
        });
    }

    function resetRoleSelection() {
        selectedRoles = new Set();
        currentRoleMode = null;

        if (selectedRolesInputs) {
            selectedRolesInputs.innerHTML = "";
        }

        updateRoleSelectionUI();
    }

    function enableRoleFlowButton() {
        if (!openRoleModalButton) {
            return;
        }

        openRoleModalButton.disabled = false;
        openRoleModalButton.className =
            "w-full py-2.5 px-4 rounded-xl " +
            "bg-[#13223a] hover:bg-[#1c3152] " +
            "text-white font-bold text-xs transition-all " +
            "flex items-center justify-center gap-2 cursor-pointer";

        openRoleModalButton.innerHTML = `
            <span>Seleccionar roles y continuar</span>
            <i class="fa-solid fa-arrow-right"></i>
        `;
    }

    function updateRoleFlowButton() {
        if (!openRoleModalButton) {
            return;
        }

        openRoleModalButton.disabled = false;
        openRoleModalButton.className =
            "w-full py-2.5 px-4 rounded-xl " +
            "bg-[#02bc4d] hover:bg-[#00a943] " +
            "text-white font-bold text-xs transition-all " +
            "flex items-center justify-center gap-2 cursor-pointer " +
            "shadow-sm shadow-[#02bc4d]/20";

        openRoleModalButton.innerHTML = `
            <i class="fa-solid fa-check"></i>
            <span>
                ${selectedRoles.size}
                ${selectedRoles.size === 1 ? "rol seleccionado" : "roles seleccionados"}
            </span>
            <i class="fa-solid fa-pen text-[10px] ml-1"></i>
        `;
    }
}
