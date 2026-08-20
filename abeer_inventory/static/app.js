document.addEventListener('DOMContentLoaded', () => {
  const button = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-menu]');
  if (button && menu) button.addEventListener('click', () => menu.classList.toggle('open'));
  document.querySelectorAll('[data-auto-submit]').forEach(el => el.addEventListener('change', () => el.form.submit()));
  document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', e => {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
  }));
  const input = document.querySelector('[data-image-input]');
  const preview = document.querySelector('[data-image-preview]');
  if (input && preview) input.addEventListener('change', () => {
    const file = input.files && input.files[0];
    if (!file) return;
    preview.src = URL.createObjectURL(file);
    preview.classList.remove('hidden');
  });
});
