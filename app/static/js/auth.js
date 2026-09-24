'use strict';
document.querySelectorAll('[data-password]').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.password);
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-label', `${visible ? 'Hide' : 'Show'} ${input.labels[0].textContent.toLowerCase()}`);
  });
});
const authForm = document.querySelector('[data-auth-form]');
const confirmInput = document.getElementById('confirm_password');
if (confirmInput) {
  const validateMatch = () => confirmInput.setCustomValidity(confirmInput.value !== document.getElementById('password').value ? "Passwords don't match." : '');
  confirmInput.addEventListener('input', validateMatch);
  document.getElementById('password').addEventListener('input', validateMatch);
}
authForm?.addEventListener('submit', () => {
  const button = authForm.querySelector('[type="submit"]');
  button.disabled = true;
  button.textContent = button.dataset.loading;
});
