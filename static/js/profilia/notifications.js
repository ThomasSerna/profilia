const successNotification = document.getElementById("profile-success-notification");
const errorNotification = document.getElementById("profile-error-notification");
const errorMessage = document.getElementById("profile-error-message");

export function showSuccessNotification() {
    errorNotification.classList.add("hidden");
    successNotification.classList.remove("hidden");
    setTimeout(() => successNotification.classList.add("hidden"), 3500);
}

export function showErrorNotification(message) {
    successNotification.classList.add("hidden");
    errorMessage.textContent = message;
    errorNotification.classList.remove("hidden");
    setTimeout(() => errorNotification.classList.add("hidden"), 4500);
}

export function hideNotifications() {
    successNotification.classList.add("hidden");
    errorNotification.classList.add("hidden");
}
