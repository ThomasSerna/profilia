import {
    hideNotifications,
    showErrorNotification,
    showSuccessNotification,
} from "./notifications.js";

export function initProfileUpload(form, onProcessed) {
    const uploadBox = document.getElementById("pdf-upload-box");
    const pdfInput = document.getElementById("pdf-input");
    const fileName = document.getElementById("selected-file-name");
    const processButton = document.getElementById("process-profile-button");
    const statusBadge = document.getElementById("profile-status-badge");

    uploadBox.addEventListener("click", () => pdfInput.click());
    pdfInput.addEventListener("change", () => handleSelectedFile(pdfInput.files[0]));

    uploadBox.addEventListener("dragover", event => {
        event.preventDefault();
        uploadBox.classList.add("border-[#02bc4d]", "bg-emerald-50");
    });

    uploadBox.addEventListener("dragleave", () => {
        uploadBox.classList.remove("border-[#02bc4d]", "bg-emerald-50");
    });

    uploadBox.addEventListener("drop", event => {
        event.preventDefault();
        uploadBox.classList.remove("border-[#02bc4d]", "bg-emerald-50");
        const file = event.dataTransfer.files[0];

        if (!file || !validateFile(file)) {
            return;
        }

        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        pdfInput.files = dataTransfer.files;
        handleSelectedFile(file);
    });

    form.addEventListener("submit", async event => {
        event.preventDefault();
        const file = pdfInput.files[0];

        if (!file || !validateFile(file)) {
            return;
        }

        setProcessingState();
        const formData = new FormData(form);

        try {
            const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                headers: { "X-CSRFToken": csrfToken },
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(
                    data.error || "Ocurrió un error procesando la hoja de vida."
                );
            }

            setProcessedState();
            showSuccessNotification();
            onProcessed(data.profile || null);
        } catch (error) {
            setReadyState();
            showErrorNotification(error.message);
        }
    });

    return { restoreProcessedState };

    function restoreProcessedState() {
        setProcessedState();
        disableProcessButton();
        statusBadge.textContent = "Perfil guardado";
    }

    function handleSelectedFile(file) {
        hideNotifications();

        if (!file) {
            fileName.textContent = "Ningún archivo seleccionado";
            disableProcessButton();
            return;
        }

        if (!validateFile(file)) {
            return;
        }

        fileName.textContent = file.name;
        setReadyState();
    }

    function validateFile(file) {
        const maxSize = 10 * 1024 * 1024;

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            pdfInput.value = "";
            fileName.textContent = "El archivo debe ser un PDF";
            disableProcessButton();
            showErrorNotification("El archivo seleccionado debe ser un PDF.");
            return false;
        }

        if (file.size > maxSize) {
            pdfInput.value = "";
            fileName.textContent = "El archivo supera los 10 MB";
            disableProcessButton();
            showErrorNotification("El archivo PDF no puede superar los 10 MB.");
            return false;
        }

        return true;
    }

    function enableProcessButton() {
        processButton.disabled = false;
        processButton.className =
            "w-full py-3 px-4 rounded-xl " +
            "bg-[#02bc4d] hover:bg-[#00a943] " +
            "text-white font-bold text-xs transition-all " +
            "flex items-center justify-center gap-2 " +
            "shadow-sm shadow-[#02bc4d]/20 cursor-pointer";

        processButton.innerHTML = `
            <i class="fa-solid fa-wand-magic-sparkles"></i>
            <span>Procesar Hoja de Vida</span>
        `;
    }

    function disableProcessButton() {
        processButton.disabled = true;
        processButton.className =
            "w-full py-3 px-4 rounded-xl " +
            "bg-slate-200 text-slate-400 " +
            "font-bold text-xs transition-all " +
            "flex items-center justify-center gap-2 cursor-not-allowed";
    }

    function setProcessingState() {
        processButton.disabled = true;
        processButton.className =
            "w-full py-3 px-4 rounded-xl " +
            "bg-[#02bc4d]/70 text-white font-bold text-xs " +
            "flex items-center justify-center gap-2 cursor-wait";

        processButton.innerHTML = `
            <i class="fa-solid fa-spinner fa-spin"></i>
            <span>Procesando hoja de vida...</span>
        `;

        statusBadge.textContent = "Procesando...";
        statusBadge.className =
            "text-[10px] px-2 py-0.5 rounded-full " +
            "bg-amber-100 text-amber-700 font-semibold";
    }

    function setProcessedState() {
        enableProcessButton();
        statusBadge.textContent = "Procesado";
        statusBadge.className =
            "text-[10px] px-2 py-0.5 rounded-full " +
            "bg-emerald-100 text-[#02bc4d] font-semibold";
    }

    function setReadyState() {
        enableProcessButton();
        statusBadge.textContent = "CV cargado";
        statusBadge.className =
            "text-[10px] px-2 py-0.5 rounded-full " +
            "bg-blue-100 text-blue-700 font-semibold";
    }
}
