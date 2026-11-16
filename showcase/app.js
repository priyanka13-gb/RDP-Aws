'use strict';
document.querySelectorAll('[data-detail]').forEach((button) => {
  button.addEventListener('click', () => {
    document.getElementById('architecture-detail').textContent = button.dataset.detail;
  });
});
