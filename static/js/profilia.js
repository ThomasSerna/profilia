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
     * El archivo JS puede cargarse desde otras páginas.
     */

    if (
        !form ||
        !uploadBox ||
        !pdfInput ||
        !processButton
    ) {
        return;
    }



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


                /*
                 * Por ahora NO utilizamos la respuesta.
                 *
                 * Solo comprobamos que el backend
                 * haya respondido correctamente.
                 */

                if (!response.ok) {

                    let message =
                        "Ocurrió un error procesando la hoja de vida.";


                    try {

                        const data =
                            await response.json();


                        if (data.error) {
                            message = data.error;
                        }

                    } catch {
                        // No necesitamos hacer nada.
                    }


                    throw new Error(message);

                }


                setProcessedState();

                showSuccessNotification();


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

            pdfInput.value = "";


            fileName.textContent =
                "El archivo debe ser un PDF";


            disableProcessButton();


            showErrorNotification(
                "El archivo seleccionado debe ser un PDF."
            );


            return false;

        }


        if (file.size > maxSize) {

            pdfInput.value = "";


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