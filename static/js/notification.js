// Function to display a toastr notification
function showToastr(type, message) {
    const notificationsContainer = document.querySelector('.notifications');
    if (!notificationsContainer) {
        console.warn('Notifications container not found.');
        return;
    }

    const toast = document.createElement('div');
    toast.classList.add('toastr-common', `toastr-${type}`);

    let iconClass = '';
    switch (type) {
        case 'success':
            iconClass = 'fa-solid fa-circle-check';
            break;
        case 'error':
            iconClass = 'fa-solid fa-circle-xmark';
            break;
        case 'warning':
            iconClass = 'fa-solid fa-triangle-exclamation';
            break;
        case 'info':
            iconClass = 'fa-solid fa-circle-info';
            break;
        default:
            iconClass = 'fa-solid fa-bell';
    }

    toast.innerHTML = `<i class="icon ${iconClass}"></i><span>${message}</span>`;
    notificationsContainer.appendChild(toast);

    // Remove the toast after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000); // Animation is 5s (0.5s slideIn + 4.5s fadeOut)
}

// Global toastr object for compatibility (if other scripts expect it)
window.toastr = {
    success: (message) => showToastr('success', message),
    error: (message) => showToastr('error', message),
    warning: (message) => showToastr('warning', message),
    info: (message) => showToastr('info', message)
};


document.addEventListener('DOMContentLoaded', () => {
    // Check for session messages (if you decide to pass them from Flask)
    const sessionSuccess = document.getElementById('session-success');
    const sessionWarning = document.getElementById('session-warning');
    const sessionInfo = document.getElementById('session-info');
    const sessionError = document.getElementById('session-error');

    if (sessionSuccess && sessionSuccess.dataset.message) {
        toastr.success(sessionSuccess.dataset.message);
    }
    if (sessionWarning && sessionWarning.dataset.message) {
        toastr.warning(sessionWarning.dataset.message);
    }
    if (sessionInfo && sessionInfo.dataset.message) {
        toastr.info(sessionInfo.dataset.message);
    }
    if (sessionError && sessionError.dataset.message) {
        toastr.error(sessionError.dataset.message);
    }
});