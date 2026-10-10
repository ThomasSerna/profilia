const PROFILE_STEP_PERCENT = 25;

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
