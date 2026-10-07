document.addEventListener("DOMContentLoaded", () => {

    /*
     * ============================================================
     * Elements
     * ============================================================
     */

    const form =
        document.getElementById("profile-form");

    const uploadBox =
        document.getElementById("pdf-upload-box");

    const pdfInput =
        document.getElementById("pdf-input");

    const fileName =
        document.getElementById("selected-file-name");

    const processButton =
        document.getElementById("process-profile-button");

    const statusBadge =
        document.getElementById("profile-status-badge");

    const successNotification =
        document.getElementById("profile-success-notification");

    const errorNotification =
        document.getElementById("profile-error-notification");

    const errorMessage =
        document.getElementById("profile-error-message");


    /*
     * Role modal
     */

    const roleModal =
        document.getElementById("role-modal");

    const closeRoleModalButton =
        document.getElementById("close-role-modal-button");

    const cancelRoleModalButton =
        document.getElementById("cancel-role-modal-button");

    const openRoleModalButton =
        document.getElementById("open-role-modal-button");

    const chooseRolesButton =
        document.getElementById("choose-roles-button");

    const recommendRolesButton =
        document.getElementById("recommend-roles-button");

    const roleSelectionSection =
        document.getElementById("role-selection-section");

    const roleSelectionTitle =
        document.getElementById("role-selection-title");

    const roleSelectionDescription =
        document.getElementById("role-selection-description");

    const roleCounter =
        document.getElementById("role-counter");

    const roleList =
        document.getElementById("role-list");

    const recommendationHint =
        document.getElementById("recommendation-hint");

    const confirmRolesButton =
        document.getElementById("confirm-roles-button");

    const selectedRolesInputs =
        document.getElementById("selected-roles-inputs");

    const careerResultsSection =
    document.getElementById("career-results-section");

    const careerResultsTitle =
        document.getElementById("career-results-title");

    const careerResults =
        document.getElementById("career-results");

    const careerRoleTemplate =
        document.getElementById("career-role-template");

    const careerRequirementTemplate =
        document.getElementById("career-requirement-template");


    if (
        !form ||
        !uploadBox ||
        !pdfInput ||
        !processButton
    ) {
        return;
    }


    const roleCards =
        Array.from(
            document.querySelectorAll(".role-option")
        );


    let processedProfile = null;

    let selectedRoles =
        new Set();

    let currentRoleMode =
        null;



    /*
     * ============================================================
     * Open file selector
     * ============================================================
     */

    uploadBox.addEventListener("click", () => {
        pdfInput.click();
    });



    /*
     * ============================================================
     * File selected
     * ============================================================
     */

    pdfInput.addEventListener("change", () => {

        const file =
            pdfInput.files[0];

        handleSelectedFile(file);

    });



    /*
     * ============================================================
     * Drag & Drop
     * ============================================================
     */

    uploadBox.addEventListener(
        "dragover",
        event => {

            event.preventDefault();

            uploadBox.classList.add(
                "border-[#02bc4d]",
                "bg-emerald-50"
            );

        }
    );


    uploadBox.addEventListener(
        "dragleave",
        () => {

            uploadBox.classList.remove(
                "border-[#02bc4d]",
                "bg-emerald-50"
            );

        }
    );


    uploadBox.addEventListener(
        "drop",
        event => {

            event.preventDefault();


            uploadBox.classList.remove(
                "border-[#02bc4d]",
                "bg-emerald-50"
            );


            const droppedFiles =
                event.dataTransfer.files;


            if (!droppedFiles.length) {
                return;
            }


            const file =
                droppedFiles[0];


            if (!validateFile(file)) {
                return;
            }


            const dataTransfer =
                new DataTransfer();


            dataTransfer.items.add(file);

            pdfInput.files =
                dataTransfer.files;


            handleSelectedFile(file);

        }
    );

    /*
     * ============================================================
     * restore saved state
     * ============================================================
     */
    function restoreSavedState() {
        const element =
            document.getElementById("saved-profile-state");

        if (!element) {
            return;
        }

        const saved = JSON.parse(element.textContent);

        if (!saved.profile) {
            return;
        }

        processedProfile = saved.profile;

        setProcessedState();
        disableProcessButton();

        statusBadge.textContent = "Perfil guardado";

        enableRoleFlowButton();

        if (saved.assessments.length === 0) {
            return;
        }

        selectedRoles = new Set(saved.role_names);
        currentRoleMode = "manual";

        setRoleModeButton(chooseRolesButton);
        updateRoleSelectionUI();
        syncSelectedRolesInputs();
        updateRoleFlowButton();

        renderAssessments(saved.assessments, false);
    }

    /*
     * ============================================================
     * Render assessment
     * ============================================================
     */

    function renderAssessments(assessments, moveFocus = true) {
    careerResults.replaceChildren();

    for (const assessment of assessments) {
        const article =
            careerRoleTemplate.content.firstElementChild.cloneNode(true);

        article.querySelector("[data-role-name]").textContent =
            assessment.role_name;

        for (const requirement of assessment.requirements) {
            const row =
                careerRequirementTemplate.content.firstElementChild.cloneNode(true);

            const found =
                requirement.status === "evidencia_en_perfil";

            row.querySelector("[data-skill-name]").textContent =
                requirement.skill;

            const badge =
                row.querySelector("[data-skill-status]");

            badge.textContent =
                found ? "Con evidencia" : "Sin evidencia";

            badge.classList.add(
                found ? "bg-emerald-50" : "bg-slate-100",
                found ? "text-emerald-800" : "text-slate-600"
            );

            const mentions = requirement.evidence.map(item => {
                const origin = item.source.startsWith("skills[")
                    ? "Habilidades"
                    : "Experiencia";

                return `${origin}: ${item.value}`;
            });

            const evidenceText =
                row.querySelector("[data-skill-evidence]");

            evidenceText.textContent =
                mentions.join(" · ");

            evidenceText.hidden =
                mentions.length === 0;

            const selector = requirement.category === "required"
                ? "[data-required-skills]"
                : "[data-preferred-skills]";

            article.querySelector(selector).append(row);
        }

        careerResults.append(article);
    }

    careerResultsSection.classList.toggle(
        "hidden",
        assessments.length === 0
    );

    if (moveFocus && assessments.length > 0) {
        careerResultsTitle.focus({ preventScroll: true });

        careerResultsSection.scrollIntoView({
            block: "start",
        });
    }
}


    /*
     * ============================================================
     * Process Profile
     * ============================================================
     */

    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const file =
                pdfInput.files[0];


            if (!file) {
                return;
            }


            if (!validateFile(file)) {
                return;
            }


            setProcessingState();


            const formData =
                new FormData(form);


            try {

                const csrfToken =
                    form.querySelector(
                        "[name=csrfmiddlewaretoken]"
                    ).value;


                const response =
                    await fetch(
                        form.action,
                        {
                            method: "POST",

                            body: formData,

                            headers: {
                                "X-CSRFToken": csrfToken
                            }
                        }
                    );


                let data = null;


                try {

                    data =
                        await response.json();

                } catch {

                    data = {};

                }


                if (!response.ok) {

                    throw new Error(
                        data.error ||
                        "Ocurrió un error procesando la hoja de vida."
                    );

                }


                processedProfile =
                    data.profile || null;


                resetRoleSelection();

                setProcessedState();

                showSuccessNotification();

                enableRoleFlowButton();


                setTimeout(
                    () => {
                        openRoleModal(true);
                    },
                    350
                );


            } catch (error) {

                setReadyState();

                showErrorNotification(
                    error.message
                );

            }

        }
    );



    /*
     * ============================================================
     * Role modal
     * ============================================================
     */

    if (openRoleModalButton) {

        openRoleModalButton.addEventListener(
            "click",
            () => {
                openRoleModal(false);
            }
        );

    }


    if (closeRoleModalButton) {

        closeRoleModalButton.addEventListener(
            "click",
            closeRoleModal
        );

    }


    if (cancelRoleModalButton) {

        cancelRoleModalButton.addEventListener(
            "click",
            closeRoleModal
        );

    }


    if (roleModal) {

        roleModal.addEventListener(
            "click",
            event => {

                if (event.target === roleModal) {
                    closeRoleModal();
                }

            }
        );

    }


    document.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Escape" &&
                roleModal &&
                !roleModal.classList.contains("hidden")
            ) {
                closeRoleModal();
            }

        }
    );



    /*
     * ============================================================
     * Manual role selection
     * ============================================================
     */

    if (chooseRolesButton) {

        chooseRolesButton.addEventListener(
            "click",
            () => {

                currentRoleMode =
                    "manual";

                setRoleModeButton(
                    chooseRolesButton
                );

                showManualRoles();

            }
        );

    }



    /*
     * ============================================================
     * Recommended roles
     * ============================================================
     */

    if (recommendRolesButton) {

        recommendRolesButton.addEventListener(
            "click",
            () => {

                currentRoleMode =
                    "recommended";

                setRoleModeButton(
                    recommendRolesButton
                );

                showRecommendedRoles();

            }
        );

    }



    /*
     * ============================================================
     * Role checkbox changes
     * ============================================================
     */

    if (roleList) {

        roleList.addEventListener(
            "change",
            event => {

                const checkbox =
                    event.target.closest(
                        ".role-checkbox"
                    );


                if (!checkbox) {
                    return;
                }


                const roleName =
                    checkbox.value;


                if (checkbox.checked) {

                    if (selectedRoles.size >= 3) {

                        checkbox.checked =
                            false;

                        return;

                    }


                    selectedRoles.add(
                        roleName
                    );

                } else {

                    selectedRoles.delete(
                        roleName
                    );

                }


                updateRoleSelectionUI();

            }
        );

    }



    /*
     * ============================================================
     * Confirm roles
     * ============================================================
     */

    if (confirmRolesButton) {
        confirmRolesButton.addEventListener("click", async () => {
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

                const csrfToken = form.querySelector(
                    "[name=csrfmiddlewaretoken]"
                ).value;

                const response = await fetch(
                    confirmRolesButton.dataset.assessmentUrl,
                    {
                        method: "POST",
                        mode: "same-origin",
                        body: formData,
                        headers: {
                            "X-CSRFToken": csrfToken,
                        },
                    }
                );

                if (response.redirected) {
                    throw new Error(
                        "Vuelve a iniciar sesión para continuar."
                    );
                }

                const data = await response.json().catch(() => ({}));

                if (!response.ok || !data.success) {
                    throw new Error(
                        data.error || "No se pudo validar la selección."
                    );
                }

                selectedRoles = new Set(
                    data.roles.map(role => role.name)
                );

                console.log("Selección validada por Django:", data);

                updateRoleSelectionUI();
                syncSelectedRolesInputs();
                closeRoleModal();
                updateRoleFlowButton();
                restoreSavedState();
                renderAssessments(data.assessments);

            } catch (error) {
                showErrorNotification(error.message);

            } finally {
                updateConfirmRolesButton();
            }
        });
    }



    /*
     * ============================================================
     * Role modal helpers
     * ============================================================
     */

    function openRoleModal(resetMode) {

        if (!roleModal) {
            return;
        }


        if (resetMode) {

            currentRoleMode =
                null;

            roleSelectionSection.classList.add(
                "hidden"
            );

            recommendationHint.classList.add(
                "hidden"
            );

            clearRoleModeButtons();

        } else if (currentRoleMode === "manual") {

            showManualRoles();

        } else if (
            currentRoleMode === "recommended"
        ) {

            showRecommendedRoles();

        }


        roleModal.classList.remove(
            "hidden"
        );


        document.body.classList.add(
            "overflow-hidden"
        );

    }



    function closeRoleModal() {

        if (!roleModal) {
            return;
        }


        roleModal.classList.add(
            "hidden"
        );


        document.body.classList.remove(
            "overflow-hidden"
        );

    }



    function setRoleModeButton(activeButton) {

        clearRoleModeButtons();


        activeButton.classList.remove(
            "border-slate-200"
        );


        activeButton.classList.add(
            "border-[#02bc4d]",
            "bg-emerald-50"
        );

    }



    function clearRoleModeButtons() {

        document
            .querySelectorAll(
                ".role-mode-button"
            )
            .forEach(button => {

                button.classList.remove(
                    "border-[#02bc4d]",
                    "bg-emerald-50"
                );


                button.classList.add(
                    "border-slate-200"
                );

            });

    }



    function showManualRoles() {

        roleSelectionSection.classList.remove(
            "hidden"
        );


        recommendationHint.classList.add(
            "hidden"
        );


        roleSelectionTitle.textContent =
            "Selecciona los roles que te interesan";


        roleSelectionDescription.textContent =
            "Puedes seleccionar hasta 3 roles.";


        const orderedCards =
            [...roleCards].sort(
                (a, b) =>
                    Number(a.dataset.originalIndex) -
                    Number(b.dataset.originalIndex)
            );


        orderedCards.forEach(card => {

            card.classList.remove(
                "hidden"
            );


            const badge =
                card.querySelector(
                    ".role-recommendation-badge"
                );


            if (badge) {
                badge.classList.add(
                    "hidden"
                );
            }


            roleList.appendChild(card);

        });


        updateRoleSelectionUI();

    }



    function showRecommendedRoles() {

        roleSelectionSection.classList.remove(
            "hidden"
        );


        recommendationHint.classList.remove(
            "hidden"
        );


        roleSelectionTitle.textContent =
            "Roles recomendados para tu perfil";


        roleSelectionDescription.textContent =
            "Selecciona hasta 3 de los roles sugeridos.";


        const scoredCards =
            roleCards
                .map(card => ({
                    card,
                    score: calculateRoleScore(card)
                }))
                .sort(
                    (a, b) => {

                        if (b.score !== a.score) {
                            return b.score - a.score;
                        }


                        return (
                            Number(
                                a.card.dataset.originalIndex
                            ) -
                            Number(
                                b.card.dataset.originalIndex
                            )
                        );

                    }
                );


        const hasMatches =
            scoredCards.some(
                item => item.score > 0
            );


        scoredCards.forEach(
            (item, index) => {

                const card =
                    item.card;

                const badge =
                    card.querySelector(
                        ".role-recommendation-badge"
                    );


                /*
                 * Show only the best five
                 * recommendations.
                 */

                if (index < 5) {

                    card.classList.remove(
                        "hidden"
                    );


                    if (badge) {

                        badge.classList.remove(
                            "hidden"
                        );

                    }

                } else {

                    card.classList.add(
                        "hidden"
                    );


                    if (badge) {

                        badge.classList.add(
                            "hidden"
                        );

                    }

                }


                roleList.appendChild(card);

            }
        );


        if (!hasMatches) {

            roleSelectionDescription.textContent =
                "No encontramos coincidencias muy claras. Estas son algunas opciones que puedes explorar.";

        }


        updateRoleSelectionUI();

    }



    /*
     * ============================================================
     * Recommendation score
     * ============================================================
     */

    function calculateRoleScore(card) {

        if (!processedProfile) {
            return 0;
        }


        const requiredSkills =
            splitDataAttribute(
                card.dataset.requiredSkills
            );


        const preferredSkills =
            splitDataAttribute(
                card.dataset.preferredSkills
            );


        const experienceAreas =
            splitDataAttribute(
                card.dataset.experienceAreas
            );


        const profileSkills =
            collectProfileSkills(
                processedProfile
            );


        const experienceText =
            collectExperienceText(
                processedProfile
            );


        let score = 0;


        requiredSkills.forEach(skill => {

            if (
                profileHasSkill(
                    profileSkills,
                    skill
                )
            ) {
                score += 4;
            }

        });


        preferredSkills.forEach(skill => {

            if (
                profileHasSkill(
                    profileSkills,
                    skill
                )
            ) {
                score += 2;
            }

        });


        experienceAreas.forEach(area => {

            const normalizedArea =
                normalizeText(area);


            if (
                normalizedArea &&
                experienceText.includes(
                    normalizedArea
                )
            ) {
                score += 1;
            }

        });


        return score;

    }



    function collectProfileSkills(profile) {

        const skills = [];


        if (
            Array.isArray(profile.skills)
        ) {

            skills.push(
                ...profile.skills
            );

        }


        if (
            Array.isArray(profile.experience)
        ) {

            profile.experience.forEach(
                experience => {

                    if (
                        Array.isArray(
                            experience.technologies
                        )
                    ) {

                        skills.push(
                            ...experience.technologies
                        );

                    }

                }
            );

        }


        return new Set(
            skills
                .map(canonicalSkill)
                .filter(Boolean)
        );

    }



    function collectExperienceText(profile) {

        if (
            !Array.isArray(
                profile.experience
            )
        ) {
            return "";
        }


        const parts = [];


        profile.experience.forEach(
            experience => {

                if (experience.role) {
                    parts.push(
                        experience.role
                    );
                }


                if (experience.description) {
                    parts.push(
                        experience.description
                    );
                }


                if (
                    Array.isArray(
                        experience.technologies
                    )
                ) {

                    parts.push(
                        ...experience.technologies
                    );

                }

            }
        );


        return normalizeText(
            parts.join(" ")
        );

    }



    function profileHasSkill(
        profileSkills,
        targetSkill
    ) {

        const target =
            canonicalSkill(
                targetSkill
            );


        if (!target) {
            return false;
        }


        return profileSkills.has(
            target
        );

    }



    function canonicalSkill(value) {

        let normalized =
            normalizeText(value);


        const aliases = {
            "springboot": "spring boot",
            "spring boot framework": "spring boot",
            "rest api": "rest apis",
            "restful api": "rest apis",
            "restful apis": "rest apis",
            "api rest": "rest apis",
            "apis rest": "rest apis",
            "js": "javascript",
            "ts": "typescript",
            "postgres": "postgresql"
        };


        if (
            normalized.includes("rest") &&
            normalized.includes("api")
        ) {
            return "rest apis";
        }


        return aliases[normalized] ||
            normalized;

    }



    function normalizeText(value) {

        return String(value || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(
                /[\u0300-\u036f]/g,
                ""
            )
            .replace(
                /[^a-z0-9+#.]+/g,
                " "
            )
            .trim();

    }



    function splitDataAttribute(value) {

        if (!value) {
            return [];
        }


        return value
            .split("|")
            .map(item => item.trim())
            .filter(Boolean);

    }



    /*
     * ============================================================
     * Role selection UI
     * ============================================================
     */

    function updateRoleSelectionUI() {

        const limitReached =
            selectedRoles.size >= 3;


        roleCards.forEach(card => {

            const checkbox =
                card.querySelector(
                    ".role-checkbox"
                );


            if (!checkbox) {
                return;
            }


            const roleName =
                checkbox.value;


            checkbox.checked =
                selectedRoles.has(
                    roleName
                );


            checkbox.disabled =
                limitReached &&
                !checkbox.checked;


            if (checkbox.checked) {

                card.classList.remove(
                    "border-slate-200"
                );


                card.classList.add(
                    "border-[#02bc4d]",
                    "bg-emerald-50"
                );

            } else {

                card.classList.remove(
                    "border-[#02bc4d]",
                    "bg-emerald-50"
                );


                card.classList.add(
                    "border-slate-200"
                );

            }


            if (checkbox.disabled) {

                card.classList.add(
                    "opacity-50",
                    "cursor-not-allowed"
                );

            } else {

                card.classList.remove(
                    "opacity-50",
                    "cursor-not-allowed"
                );

            }

        });


        if (roleCounter) {

            roleCounter.textContent =
                `${selectedRoles.size} / 3`;

        }


        updateConfirmRolesButton();

    }



    function updateConfirmRolesButton() {

        if (!confirmRolesButton) {
            return;
        }


        if (selectedRoles.size === 0) {

            confirmRolesButton.disabled =
                true;


            confirmRolesButton.className =
                "px-5 py-2.5 rounded-xl " +
                "bg-slate-200 text-slate-400 " +
                "text-xs font-bold flex items-center gap-2 " +
                "cursor-not-allowed transition";

            return;

        }


        confirmRolesButton.disabled =
            false;


        confirmRolesButton.className =
            "px-5 py-2.5 rounded-xl " +
            "bg-[#02bc4d] hover:bg-[#00a943] " +
            "text-white text-xs font-bold " +
            "flex items-center gap-2 " +
            "cursor-pointer transition " +
            "shadow-sm shadow-[#02bc4d]/20";

    }



    function syncSelectedRolesInputs() {

        if (!selectedRolesInputs) {
            return;
        }


        selectedRolesInputs.innerHTML =
            "";


        selectedRoles.forEach(
            roleName => {

                const input =
                    document.createElement(
                        "input"
                    );


                input.type =
                    "hidden";


                input.name =
                    "roles";


                input.value =
                    roleName;


                selectedRolesInputs.appendChild(
                    input
                );

            }
        );

    }



    function resetRoleSelection() {

        selectedRoles =
            new Set();


        currentRoleMode =
            null;


        if (selectedRolesInputs) {

            selectedRolesInputs.innerHTML =
                "";

        }


        updateRoleSelectionUI();

    }



    /*
     * ============================================================
     * Role flow button
     * ============================================================
     */

    function enableRoleFlowButton() {

        if (!openRoleModalButton) {
            return;
        }


        openRoleModalButton.disabled =
            false;


        openRoleModalButton.className =
            "w-full py-2.5 px-4 rounded-xl " +
            "bg-[#13223a] hover:bg-[#1c3152] " +
            "text-white font-bold text-xs " +
            "transition-all flex items-center " +
            "justify-center gap-2 cursor-pointer";


        openRoleModalButton.innerHTML = `
            <span>Seleccionar roles y continuar</span>
            <i class="fa-solid fa-arrow-right"></i>
        `;

    }



    function updateRoleFlowButton() {

        if (!openRoleModalButton) {
            return;
        }


        openRoleModalButton.disabled =
            false;


        openRoleModalButton.className =
            "w-full py-2.5 px-4 rounded-xl " +
            "bg-[#02bc4d] hover:bg-[#00a943] " +
            "text-white font-bold text-xs " +
            "transition-all flex items-center " +
            "justify-center gap-2 cursor-pointer " +
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



    /*
     * ============================================================
     * File Helpers
     * ============================================================
     */

    function handleSelectedFile(file) {

        hideNotifications();


        if (!file) {

            fileName.textContent =
                "Ningún archivo seleccionado";


            disableProcessButton();

            return;

        }


        if (!validateFile(file)) {
            return;
        }


        fileName.textContent =
            file.name;


        enableProcessButton();


        statusBadge.textContent =
            "CV cargado";


        statusBadge.className =
            "text-[10px] px-2 py-0.5 rounded-full " +
            "bg-blue-100 text-blue-700 font-semibold";

    }



    function validateFile(file) {

        const maxSize =
            10 * 1024 * 1024;


        if (
            !file.name
                .toLowerCase()
                .endsWith(".pdf")
        ) {

            pdfInput.value =
                "";


            fileName.textContent =
                "El archivo debe ser un PDF";


            disableProcessButton();


            showErrorNotification(
                "El archivo seleccionado debe ser un PDF."
            );


            return false;

        }


        if (file.size > maxSize) {

            pdfInput.value =
                "";


            fileName.textContent =
                "El archivo supera los 10 MB";


            disableProcessButton();


            showErrorNotification(
                "El archivo PDF no puede superar los 10 MB."
            );


            return false;

        }


        return true;

    }



    /*
     * ============================================================
     * Button States
     * ============================================================
     */

    function enableProcessButton() {

        processButton.disabled =
            false;


        processButton.className =
            "w-full py-3 px-4 rounded-xl " +
            "bg-[#02bc4d] hover:bg-[#00a943] " +
            "text-white font-bold text-xs transition-all " +
            "flex items-center justify-center gap-2 " +
            "shadow-sm shadow-[#02bc4d]/20 " +
            "cursor-pointer";


        processButton.innerHTML = `
            <i class="fa-solid fa-wand-magic-sparkles"></i>
            <span>Procesar Hoja de Vida</span>
        `;

    }



    function disableProcessButton() {

        processButton.disabled =
            true;


        processButton.className =
            "w-full py-3 px-4 rounded-xl " +
            "bg-slate-200 text-slate-400 " +
            "font-bold text-xs transition-all " +
            "flex items-center justify-center gap-2 " +
            "cursor-not-allowed";

    }



    function setProcessingState() {

        processButton.disabled =
            true;


        processButton.className =
            "w-full py-3 px-4 rounded-xl " +
            "bg-[#02bc4d]/70 text-white " +
            "font-bold text-xs " +
            "flex items-center justify-center gap-2 " +
            "cursor-wait";


        processButton.innerHTML = `
            <i class="fa-solid fa-spinner fa-spin"></i>
            <span>Procesando hoja de vida...</span>
        `;


        statusBadge.textContent =
            "Procesando...";


        statusBadge.className =
            "text-[10px] px-2 py-0.5 rounded-full " +
            "bg-amber-100 text-amber-700 font-semibold";

    }



    function setProcessedState() {

        enableProcessButton();


        statusBadge.textContent =
            "Procesado";


        statusBadge.className =
            "text-[10px] px-2 py-0.5 rounded-full " +
            "bg-emerald-100 text-[#02bc4d] font-semibold";

    }



    function setReadyState() {

        enableProcessButton();


        statusBadge.textContent =
            "CV cargado";


        statusBadge.className =
            "text-[10px] px-2 py-0.5 rounded-full " +
            "bg-blue-100 text-blue-700 font-semibold";

    }



    /*
     * ============================================================
     * Notifications
     * ============================================================
     */

    function showSuccessNotification() {

        errorNotification.classList.add(
            "hidden"
        );


        successNotification.classList.remove(
            "hidden"
        );


        setTimeout(
            () => {

                successNotification.classList.add(
                    "hidden"
                );

            },
            3500
        );

    }



    function showErrorNotification(message) {

        successNotification.classList.add(
            "hidden"
        );


        errorMessage.textContent =
            message;


        errorNotification.classList.remove(
            "hidden"
        );


        setTimeout(
            () => {

                errorNotification.classList.add(
                    "hidden"
                );

            },
            4500
        );

    }



    function hideNotifications() {

        successNotification.classList.add(
            "hidden"
        );


        errorNotification.classList.add(
            "hidden"
        );

    }

});