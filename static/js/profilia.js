import { initProfileUpload } from "./profilia/profile-upload.js";
import { initRoleSelection } from "./profilia/role-selection.js";
import { initAccountMenus, markProfileCompleted } from "./profilia/sidebar.js";

document.addEventListener("DOMContentLoaded", () => {
    initAccountMenus();
    const form = document.getElementById("profile-form");

    if (
        !form ||
        !document.getElementById("pdf-upload-box") ||
        !document.getElementById("pdf-input") ||
        !document.getElementById("process-profile-button")
    ) {
        return;
    }

    let busy = false;
    let roles;
    let upload;
    const operations = {
        isBusy: () => busy,
        setBusy(value) {
            busy = value;
            roles?.setBusy(value);
            upload?.setBusy(value);
        },
        invalidateProfile: () => roles.invalidateProfile(),
    };
    roles = initRoleSelection(form, operations);
    upload = initProfileUpload(form, data => {
        if (!data.profile_ready) {
            window.location.reload();
            return;
        }
        markProfileCompleted();
        roles.setProfile(data);

        if (data.profile_ready && !(data.assessments || []).length) {
            roles.openRoleModal(true);
        }
    }, operations);

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

        upload.restoreSavedState(saved);
        roles.setProfile(saved);
    }
});
