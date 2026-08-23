document.addEventListener("DOMContentLoaded", () => {

    const uploadBox =
        document.getElementById("pdf-upload-box");

    const pdfInput =
        document.getElementById("pdf-input");

    const fileName =
        document.getElementById("selected-file-name");


    if (!uploadBox || !pdfInput) {
        return;
    }


    uploadBox.addEventListener("click", () => {
        pdfInput.click();
    });


    pdfInput.addEventListener("change", () => {

        const file =
            pdfInput.files[0];


        if (!file) {

            fileName.textContent =
                "Ningún archivo seleccionado";

            return;

        }


        fileName.textContent =
            file.name;

    });

});