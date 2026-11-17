const PROFILE_STEP_PERCENT = 25;
const APPLICATIONS_STEP_PERCENT = 75;
const SIDEBAR_STORAGE_KEY = "profilia.sidebar.collapsed";

export function initSidebarToggle() {
    const sidebar = document.getElementById("app-sidebar");
    const toggles = Array.from(document.querySelectorAll("[data-sidebar-toggle]"));
    const backdrop = document.querySelector("[data-sidebar-backdrop]");
    if (!sidebar || !toggles.length) {
        return;
    }

    const root = document.documentElement;

    function isDesktop() {
        return window.innerWidth >= 1024;
    }

    function isSidebarOpen() {
        if (isDesktop()) {
            return root.dataset.sidebarCollapsed !== "true";
        }
        return root.dataset.sidebarMobileOpen === "true";
    }

    function syncAria() {
        const open = isSidebarOpen();
        toggles.forEach(btn => {
            btn.setAttribute("aria-expanded", String(open));
        });
    }

    function setSidebarState(open) {
        if (isDesktop()) {
            if (open) {
                delete root.dataset.sidebarCollapsed;
            } else {
                root.dataset.sidebarCollapsed = "true";
            }
            try {
                localStorage.setItem(SIDEBAR_STORAGE_KEY, open ? "false" : "true");
            } catch {
                // Ignore storage quota or private-mode errors.
            }
        } else if (open) {
            root.dataset.sidebarMobileOpen = "true";
        } else {
            delete root.dataset.sidebarMobileOpen;
        }

        syncAria();
        window.dispatchEvent(new CustomEvent("profilia:sidebar-change", { detail: { open } }));
    }

    toggles.forEach(btn => {
        btn.addEventListener("click", () => {
            setSidebarState(!isSidebarOpen());
        });
    });

    backdrop?.addEventListener("click", () => {
        if (!isDesktop()) {
            setSidebarState(false);
        }
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !isDesktop() && root.dataset.sidebarMobileOpen === "true") {
            setSidebarState(false);
            document.getElementById("sidebar-open-btn")?.focus();
        }
    });

    window.addEventListener("resize", () => {
        if (isDesktop() && root.dataset.sidebarMobileOpen === "true") {
            delete root.dataset.sidebarMobileOpen;
        }
        syncAria();
    });

    syncAria();
}

export function initAccountMenus() {
    initSidebarToggle();

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
    const current = getCurrentProgress();
    if (current < PROFILE_STEP_PERCENT) {
        setProgress(PROFILE_STEP_PERCENT, "Vacantes");
    }
}

export function markApplicationsCompleted() {
    const badge = document.getElementById("applications-nav-badge");
    if (badge) {
        badge.textContent = "Completado";
        badge.className = "text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 font-semibold bg-emerald-900 text-emerald-300";
    }
    setProgress(APPLICATIONS_STEP_PERCENT, "Seguimiento");
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

function getCurrentProgress() {
    const bar = document.getElementById("flow-progress-bar");
    if (!bar) {
        return 0;
    }
    const match = /(\d+)/.exec(bar.style.width || "");
    return match ? Number(match[1]) : 0;
}

export function setProgress(percent, stageLabel) {
    const bar = document.getElementById("flow-progress-bar");
    const text = document.getElementById("flow-progress-text");
    const stage = document.getElementById("flow-progress-stage");
    if (bar) {
        bar.style.width = `${percent}%`;
    }
    if (text) {
        text.textContent = `Progreso total: ${percent}%`;
    }
    if (stage && stageLabel) {
        stage.textContent = stageLabel;
    }
}
