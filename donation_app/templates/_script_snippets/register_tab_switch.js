// Auto switch to register tab if register_error is present
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.register-error')) {
        document.getElementById('register-tab').click();
    }
}); 