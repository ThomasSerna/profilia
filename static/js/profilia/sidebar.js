const PROFILE_STEP_PERCENT = 25;

export function initAccountMenus() {
    document.querySelectorAll("[data-account-dropdown]").forEach(container => {
        const toggle = container.querySelector("[data-account-toggle]");
        const panel = container.querySelector("[data-account-panel]");
        const icon = container.querySelector("[data-account-icon]");

        function setOpen(open) {
            panel.classList.toggle("hidden", !open);
            toggle.setAttribute("aria-expanded", String(open));
            icon?.classList.toggle("rotate-180", open);
        }

        toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));
        document.addEventListener("click", event => {
            if (!container.contains(event.target)) {
                setOpen(false);
            }
        });
        container.addEventListener("keydown", event => {
            if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
                setOpen(false);
                toggle.focus();
            }
        });
        container.addEventListener("focusout", event => {
            if (!container.contains(event.relatedTarget)) {
                setOpen(false);
            }
        });
    });
}

export function markProfileCompleted() {
    setProfileBadge();
    unlockVacancyNav();
    setProgress(PROFILE_STEP_PERCENT);
}

function setProfileBadge() {
    const badge = document.getElementById("profile-nav-badge");
    if (!badge) {
        return;
    }
    badge.textContent = "Completado";
    badge.className = "text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-900 text-emerald-300";
}

function unlockVacancyNav() {
    const locked = document.getElementById("vacancies-nav-locked");
    const template = document.getElementById("vacancies-nav-unlocked-template");
    if (!locked || !template) {
        return;
    }

    const fragment = template.content.cloneNode(true);
    const link = fragment.querySelector("a");
    if (!link) {
        return;
    }

    link.href = link.dataset.vacanciesUrl;
    locked.replaceWith(fragment);
    template.remove();
}

function setProgress(percent) {
    const bar = document.getElementById("flow-progress-bar");
    const text = document.getElementById("flow-progress-text");
    if (bar) {
        bar.style.width = `${percent}%`;
    }
    if (text) {
        text.textContent = `Progreso total: ${percent}%`;
    }
}
