import { renderAssessments } from "./profilia/career-results.js";
import { initProfileUpload } from "./profilia/profile-upload.js";
import { initRoleSelection } from "./profilia/role-selection.js";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("profile-form");

    if (
        !form ||
        !document.getElementById("pdf-upload-box") ||
        !document.getElementById("pdf-input") ||
        !document.getElementById("process-profile-button")
    ) {
        return;
    }

    const roles = initRoleSelection(form);
    const upload = initProfileUpload(form, profile => {
        roles.setProfile(profile);
        setTimeout(() => roles.openRoleModal(true), 350);
    });

    restoreSavedState();

    function restoreSavedState() {
        const element = document.getElementById("saved-profile-state");

        if (!element) {
            return;
        }

        const saved = JSON.parse(element.textContent);

        if (!saved.profile) {
            return;
        }

        upload.restoreProcessedState();
        roles.setProfile(saved.profile);

        if (saved.assessments.length > 0) {
            roles.restoreSelection(saved.role_names);
            renderAssessments(saved.assessments, false);
        }
    }
});
