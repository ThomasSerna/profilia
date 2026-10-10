const form = document.getElementById("profile-editor-form");

if (form) {
    const status = document.getElementById("profile-save-status");
    const saveButton = form.querySelector("button[type=submit]");
    const saveError = document.getElementById("profile-save-error");
    const collections = [...form.querySelectorAll("[data-collection]")];
    let dirty = form.dataset.hasErrors === "true";
    let submitting = false;

    function markDirty() {
        dirty = true;
        status.textContent = "Tienes cambios sin guardar.";
    }

    function updateCollection(section) {
        const entries = [...section.querySelector("[data-entries]").children].filter(entry => !entry.hidden);
        section.querySelector("[data-empty-collection]").hidden = entries.length > 0;
        entries.forEach((entry, index) => {
            entry.querySelector("[data-entry-number]").textContent = index + 1;
            entry.querySelector("[data-remove-entry]").setAttribute("aria-label", `Eliminar ${section.dataset.entryLabel.toLowerCase()} ${index + 1}`);
        });
    }

    collections.forEach(section => {
        section.querySelectorAll("[data-profile-entry]").forEach(entry => {
            if (entry.querySelector("input[name$='-DELETE']").checked) {
                entry.hidden = true;
            }
        });
        updateCollection(section);
        section.addEventListener("click", event => {
            const add = event.target.closest("[data-add-entry]");
            const remove = event.target.closest("[data-remove-entry]");
            if (add) {
                const total = section.querySelector("input[name$='-TOTAL_FORMS']");
                const maximum = Number(section.querySelector("input[name$='-MAX_NUM_FORMS']").value);
                const index = Number(total.value);
                if (maximum && index >= maximum) {
                    section.querySelector("[data-collection-status]").textContent = "Llegaste al límite de esta sección. Edita una entrada existente o guarda tus cambios antes de añadir otra.";
                    return;
                }
                const template = section.querySelector("[data-empty-form]");
                const fragment = document.createElement("template");
                fragment.innerHTML = template.innerHTML.replaceAll("__prefix__", String(index));
                const entry = fragment.content.firstElementChild;
                section.querySelector("[data-entries]").append(entry);
                total.value = index + 1;
                updateCollection(section);
                markDirty();
                entry.querySelector("input:not([type=checkbox]):not([type=hidden]), textarea, select")?.focus();
            } else if (remove) {
                const entry = remove.closest("[data-profile-entry]");
                entry.querySelector("input[name$='-DELETE']").checked = true;
                entry.hidden = true;
                updateCollection(section);
                markDirty();
                section.querySelector("[data-add-entry]").focus();
            }
        });
    });

    form.addEventListener("input", markDirty);
    form.addEventListener("change", markDirty);
    function clearErrors() {
        saveError.hidden = true;
        document.getElementById("profile-error-summary")?.setAttribute("hidden", "");
        form.querySelectorAll(".profile-field-errors").forEach(element => element.replaceChildren());
        form.querySelectorAll("[aria-invalid]").forEach(control => control.removeAttribute("aria-invalid"));
    }

    function showSaveError(message, data = {}, conflict = false) {
        saveError.replaceChildren();
        const content = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = conflict ? "Tu perfil cambió en otra ventana." : "No pudimos guardar tus cambios.";
        const explanation = document.createElement("p");
        explanation.textContent = message;
        const preserved = document.createElement("p");
        preserved.textContent = "Tus cambios siguen en esta página.";
        content.append(title, explanation, preserved);
        const summary = document.createElement("ul");
        for (const [name, errors] of Object.entries(data.field_errors || {})) {
            const control = form.elements.namedItem(name);
            const field = control?.closest(".profile-field");
            if (field) {
                control.setAttribute("aria-invalid", "true");
                const errorId = `${control.id}-errors`;
                let errorList = document.getElementById(errorId);
                if (!errorList) {
                    errorList = document.createElement("ul");
                    errorList.id = errorId;
                    errorList.className = "profile-field-errors";
                    field.append(errorList);
                }
                const described = new Set((control.getAttribute("aria-describedby") || "").split(" ").filter(Boolean));
                described.add(errorId);
                control.setAttribute("aria-describedby", [...described].join(" "));
                errors.forEach(error => {
                    const item = document.createElement("li");
                    item.textContent = error;
                    errorList.append(item);
                });
            }
            errors.forEach(error => {
                const item = document.createElement("li");
                const link = document.createElement(control?.id ? "a" : "span");
                if (control?.id) {
                    link.href = `#${control.id}`;
                }
                const label = control?.labels?.[0]?.textContent.trim();
                link.textContent = label ? `${label}: ${error}` : error;
                item.append(link);
                summary.append(item);
            });
        }
        (data.non_field_errors || []).forEach(error => {
            const item = document.createElement("li");
            item.textContent = error;
            summary.append(item);
        });
        if (summary.children.length) {
            content.append(summary);
        }
        if (conflict) {
            form.dataset.conflict = "true";
            const recovery = document.createElement("p");
            recovery.textContent = "Copia primero los cambios que quieras conservar. ";
            const link = document.createElement("a");
            link.href = form.action;
            link.textContent = "Ver el perfil más reciente";
            recovery.append(link);
            content.append(recovery);
        }
        saveError.append(content);
        saveError.hidden = false;
        saveError.focus();
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (submitting || form.dataset.conflict === "true") {
            return;
        }
        clearErrors();
        const body = new FormData(form);
        const controls = [...form.querySelectorAll("input, textarea, select, button")].map(control => ({ control, disabled: control.disabled }));
        submitting = true;
        form.dataset.saving = "true";
        form.setAttribute("aria-busy", "true");
        controls.forEach(({ control }) => { control.disabled = true; });
        saveButton.querySelector("span").textContent = "Guardando cambios…";
        status.textContent = "Profilia está guardando tu perfil.";
        try {
            const response = await fetch(form.action, { method: "POST", mode: "same-origin", body, headers: { Accept: "application/json" } });
            if (response.redirected || response.status === 401 || response.status === 403) {
                throw new Error("Tu sesión venció o no permite esta operación. Conserva tus cambios y vuelve a iniciar sesión.");
            }
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success) {
                showSaveError(data.error || "Vuelve a intentarlo en unos momentos.", data, response.status === 409);
                dirty = true;
                status.textContent = "Tus cambios aún no se han guardado.";
                return;
            }
            dirty = false;
            status.textContent = "Tu perfil se actualizó.";
            window.location.assign(data.redirect_url || form.action);
        } catch (error) {
            showSaveError(error instanceof TypeError ? "No pudimos conectar con Profilia. Comprueba tu conexión y vuelve a guardar." : error.message);
            dirty = true;
            status.textContent = "Tus cambios aún no se han guardado.";
        } finally {
            submitting = false;
            form.dataset.saving = "false";
            form.setAttribute("aria-busy", "false");
            controls.forEach(({ control, disabled }) => { control.disabled = disabled; });
            saveButton.disabled = form.dataset.conflict === "true";
            saveButton.querySelector("span").textContent = "Guardar cambios";
        }
    });
    window.addEventListener("beforeunload", event => {
        if (dirty) {
            event.preventDefault();
            event.returnValue = "";
        }
    });
    document.addEventListener("click", event => {
        const link = event.target.closest("a[href]");
        if (submitting && link && !event.metaKey && !event.ctrlKey && !event.shiftKey && link.target !== "_blank") {
            event.preventDefault();
            status.textContent = "Espera a que termine el guardado antes de salir.";
            return;
        }
        if (!dirty || submitting || !link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.getAttribute("href").startsWith("#") || link.target === "_blank") {
            return;
        }
        if (!window.confirm("Tienes cambios sin guardar. ¿Quieres salir y descartarlos?")) {
            event.preventDefault();
        } else {
            dirty = false;
        }
    });
    document.querySelectorAll("form[action]").forEach(other => {
        if (other !== form) {
            other.addEventListener("submit", event => {
                if (submitting) {
                    event.preventDefault();
                    status.textContent = "Espera a que termine el guardado antes de salir.";
                } else if (dirty && !window.confirm("Tienes cambios sin guardar. ¿Quieres salir y descartarlos?")) {
                    event.preventDefault();
                } else {
                    dirty = false;
                }
            });
        }
    });
    window.addEventListener("pageshow", event => {
        if (event.persisted) {
            submitting = false;
            form.dataset.saving = "false";
            saveButton.disabled = form.dataset.conflict === "true";
            saveButton.querySelector("span").textContent = "Guardar cambios";
            status.textContent = dirty ? "Tienes cambios sin guardar." : "Tus cambios se guardarán cuando tú decidas.";
        }
    });
    if (form.dataset.hasErrors === "true") {
        document.getElementById("profile-error-summary")?.focus();
    }

    const links = [...document.querySelectorAll(".profile-section-index nav a")];
    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(entries => {
            entries.filter(entry => entry.isIntersecting).forEach(entry => {
                links.forEach(link => {
                    if (link.hash === `#${entry.target.closest(".profile-section").id}`) {
                        link.setAttribute("aria-current", "location");
                    } else {
                        link.removeAttribute("aria-current");
                    }
                });
            });
        }, { root: form.closest("main").querySelector(".overflow-y-auto"), rootMargin: "0px 0px -55% 0px", threshold: 0 });
        form.querySelectorAll(".profile-section-heading").forEach(heading => observer.observe(heading));
    }
}
