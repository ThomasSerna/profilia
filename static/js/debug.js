document.addEventListener("DOMContentLoaded", () => {

    /*
     * ============================================================
     * Configuration
     * ============================================================
     */

    const agentConfig = {

        profile: {
            title: "Agente de Perfil",
            description: "Ejecuta manualmente ProfileGraph",
            available: true
        },

        vacancies: {
            title: "Agente de Vacantes",
            description: "Matching, normalización y scoring de vacantes",
            available: false
        },

        application: {
            title: "Agente de Postulación",
            description: "Pruebas del proceso automático de postulación",
            available: false
        },

        followup: {
            title: "Agente de Seguimiento",
            description: "Pruebas de seguimiento de postulaciones",
            available: false
        },

        state: {
            title: "LangGraph State Inspector",
            description: "Estado retornado por la última ejecución",
            available: true
        }

    };


    let lastGraphState = null;



    /*
     * ============================================================
     * Elements
     * ============================================================
     */

    const navigationItems =
        document.querySelectorAll(".debug-nav-item");

    const panels =
        document.querySelectorAll(".debug-panel");

    const debugTitle =
        document.getElementById("debug-title");

    const debugDescription =
        document.getElementById("debug-description");

    const debugAgentStatus =
        document.getElementById("debug-agent-status");


    const profileForm =
        document.getElementById("profile-debug-form");

    const profilePdf =
        document.getElementById("profile-pdf");

    const pdfFileName =
        document.getElementById("pdf-file-name");

    const executeProfileButton =
        document.getElementById("execute-profile-button");


    const executionStatus =
        document.getElementById("execution-status");

    const emptyOutput =
        document.getElementById("empty-output");

    const errorOutput =
        document.getElementById("error-output");

    const errorMessage =
        document.getElementById("error-message");

    const profileOutput =
        document.getElementById("profile-output");


    const rawTextCard =
        document.getElementById("raw-text-card");

    const rawTextOutput =
        document.getElementById("raw-text-output");


    const graphStateOutput =
        document.getElementById("graph-state-output");


    const executionConsole =
        document.getElementById("execution-console");

    const clearConsole =
        document.getElementById("clear-console");



    /*
     * ============================================================
     * Navigation
     * ============================================================
     */

    navigationItems.forEach(item => {

        item.addEventListener("click", () => {

            const agent = item.dataset.agent;

            selectAgent(agent);

        });

    });


    function selectAgent(agent) {

        panels.forEach(panel => {
            panel.classList.add("hidden");
        });


        navigationItems.forEach(item => {

            item.classList.remove(
                "bg-[#02bc4d]",
                "text-white"
            );

            item.classList.add(
                "text-slate-400"
            );

        });


        const panel =
            document.getElementById(`panel-${agent}`);

        const navigation =
            document.getElementById(`nav-${agent}`);


        if (panel) {
            panel.classList.remove("hidden");
        }


        if (navigation) {

            navigation.classList.remove(
                "text-slate-400"
            );

            navigation.classList.add(
                "bg-[#02bc4d]",
                "text-white"
            );

        }


        const config = agentConfig[agent];

        debugTitle.textContent =
            config.title;

        debugDescription.textContent =
            config.description;


        if (config.available) {

            debugAgentStatus.textContent =
                "Disponible";

            debugAgentStatus.className =
                "px-2 py-0.5 rounded-full " +
                "bg-emerald-100 text-[#02bc4d] " +
                "text-[10px] font-bold";

        } else {

            debugAgentStatus.textContent =
                "Pendiente";

            debugAgentStatus.className =
                "px-2 py-0.5 rounded-full " +
                "bg-amber-100 text-amber-700 " +
                "text-[10px] font-bold";

        }


        if (agent === "state") {

            graphStateOutput.textContent =
                lastGraphState
                    ? JSON.stringify(
                        lastGraphState,
                        null,
                        2
                    )
                    : "No se ha ejecutado ningún grafo.";

        }

    }



    /*
     * ============================================================
     * PDF input
     * ============================================================
     */

    profilePdf.addEventListener("change", () => {

        const file =
            profilePdf.files[0];


        if (!file) {

            pdfFileName.textContent =
                "Seleccionar PDF";

            return;

        }


        pdfFileName.textContent =
            file.name;

    });



    /*
     * ============================================================
     * Profile Graph
     * ============================================================
     */

    profileForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const file =
                profilePdf.files[0];


            if (!file) {

                showError(
                    "Debes seleccionar un archivo PDF."
                );

                return;

            }


            if (!file.name.toLowerCase().endsWith(".pdf")) {

                showError(
                    "El archivo debe ser un PDF."
                );

                return;

            }


            const formData =
                new FormData(profileForm);


            setLoading(true);

            hideOutputs();


            writeConsole(
                "GRAPH",
                "Ejecutando ProfileGraph...",
                "text-blue-400"
            );


            try {

                const csrfToken =
                    profileForm.querySelector(
                        "[name=csrfmiddlewaretoken]"
                    ).value;


                const response =
                    await fetch(
                        profileForm.action,
                        {
                            method: "POST",

                            body: formData,

                            headers: {
                                "X-CSRFToken": csrfToken
                            }
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok || !data.success) {

                    throw new Error(
                        data.error ||
                        "Ocurrió un error durante la ejecución."
                    );

                }


                renderProfile(data);


                lastGraphState = {
                    pdf_path: "<temporary_file_removed>",
                    raw_text: data.raw_text,
                    profile: data.profile
                };


                setStatus(
                    "Success",
                    "success"
                );


                writeConsole(
                    "SUCCESS",
                    "ProfileGraph ejecutado correctamente.",
                    "text-[#00d461]"
                );


            } catch (error) {

                showError(error.message);


                setStatus(
                    "Error",
                    "error"
                );


                writeConsole(
                    "ERROR",
                    error.message,
                    "text-red-400"
                );

            } finally {

                setLoading(false);

            }

        }
    );



    /*
     * ============================================================
     * Render profile
     * ============================================================
     */

    function renderProfile(data) {

        emptyOutput.classList.add("hidden");
        errorOutput.classList.add("hidden");

        profileOutput.classList.remove("hidden");


        const profile =
            data.profile || {};


        setText(
            "output-name",
            profile.name
        );

        setText(
            "output-email",
            profile.email
        );

        setText(
            "output-phone",
            profile.phone
        );

        setText(
            "output-filename",
            data.filename
        );


        renderTags(
            "output-skills",
            profile.skills,
            true
        );


        renderList(
            "output-education",
            profile.education
        );


        renderList(
            "output-experience",
            profile.experience
        );


        renderTags(
            "output-languages",
            profile.languages,
            false
        );


        if (data.raw_text) {

            rawTextOutput.textContent =
                data.raw_text;

            rawTextCard.classList.remove(
                "hidden"
            );

        } else {

            rawTextCard.classList.add(
                "hidden"
            );

        }

    }



    function setText(elementId, value) {

        const element =
            document.getElementById(elementId);


        element.textContent =
            value || "null";

    }



    function renderTags(
        containerId,
        values,
        green
    ) {

        const container =
            document.getElementById(containerId);


        container.innerHTML = "";


        if (!values || values.length === 0) {

            const empty =
                document.createElement("span");

            empty.className =
                "text-xs text-slate-400";

            empty.textContent = "[]";

            container.appendChild(empty);

            return;

        }


        values.forEach(value => {

            const tag =
                document.createElement("span");


            if (green) {

                tag.className =
                    "px-2.5 py-1 rounded-md " +
                    "bg-emerald-50 border border-emerald-200 " +
                    "text-[#02bc4d] text-[10px] font-bold";

            } else {

                tag.className =
                    "px-2.5 py-1 rounded-md " +
                    "bg-slate-100 border border-slate-200 " +
                    "text-slate-700 text-[10px]";

            }


            tag.textContent = value;

            container.appendChild(tag);

        });

    }



    function renderList(containerId, values) {

        const container =
            document.getElementById(containerId);


        container.innerHTML = "";


        if (!values || values.length === 0) {

            const empty =
                document.createElement("p");

            empty.className =
                "text-xs text-slate-400";

            empty.textContent = "[]";

            container.appendChild(empty);

            return;

        }


        values.forEach(value => {

            const item =
                document.createElement("div");


            item.className =
                "text-xs bg-slate-50 " +
                "border border-slate-200 " +
                "rounded-lg px-3 py-2";


            item.textContent = value;


            container.appendChild(item);

        });

    }



    /*
     * ============================================================
     * Output helpers
     * ============================================================
     */

    function hideOutputs() {

        emptyOutput.classList.add("hidden");
        errorOutput.classList.add("hidden");
        profileOutput.classList.add("hidden");
        rawTextCard.classList.add("hidden");

    }



    function showError(message) {

        emptyOutput.classList.add("hidden");
        profileOutput.classList.add("hidden");

        errorMessage.textContent =
            message;

        errorOutput.classList.remove(
            "hidden"
        );

    }



    function setLoading(loading) {

        executeProfileButton.disabled =
            loading;


        if (loading) {

            executeProfileButton.classList.add(
                "opacity-60",
                "cursor-not-allowed"
            );


            executeProfileButton.innerHTML = `
                <i class="fa-solid fa-spinner fa-spin"></i>
                <span>Ejecutando...</span>
            `;


            setStatus(
                "Running",
                "running"
            );

        } else {

            executeProfileButton.classList.remove(
                "opacity-60",
                "cursor-not-allowed"
            );


            executeProfileButton.innerHTML = `
                <i class="fa-solid fa-play"></i>
                <span>Ejecutar Agente de Perfil</span>
            `;

        }

    }



    function setStatus(text, type) {

        executionStatus.textContent =
            text;


        const baseClasses =
            "px-2.5 py-1 rounded-full " +
            "text-[10px] font-bold";


        if (type === "success") {

            executionStatus.className =
                baseClasses +
                " bg-emerald-100 text-[#02bc4d]";

        } else if (type === "error") {

            executionStatus.className =
                baseClasses +
                " bg-red-100 text-red-700";

        } else if (type === "running") {

            executionStatus.className =
                baseClasses +
                " bg-blue-100 text-blue-700";

        } else {

            executionStatus.className =
                baseClasses +
                " bg-slate-100 text-slate-500";

        }

    }



    /*
     * ============================================================
     * Console
     * ============================================================
     */

    function writeConsole(
        type,
        message,
        colorClass
    ) {

        const line =
            document.createElement("p");


        const tag =
            document.createElement("span");


        tag.className =
            colorClass;

        tag.textContent =
            `[${type}]`;


        line.appendChild(tag);

        line.appendChild(
            document.createTextNode(
                ` ${message}`
            )
        );


        executionConsole.appendChild(line);


        executionConsole.scrollTop =
            executionConsole.scrollHeight;

    }



    clearConsole.addEventListener(
        "click",
        () => {

            executionConsole.innerHTML = `
                <p>
                    <span class="text-[#00d461]">
                        [SYSTEM]
                    </span>
                    Console cleared.
                </p>
            `;

        }
    );

});