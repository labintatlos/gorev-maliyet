'use strict';

(() => {
  const STORAGE_KEY = 'gorev-maliyet-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  function savedTheme() {
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      return value === 'light' || value === 'dark' ? value : null;
    } catch (_) {
      return null;
    }
  }

  function updateButtons(theme) {
    const nextIsDark = theme === 'light';
    const label = nextIsDark ? 'Karanlık görünüm' : 'Aydınlık görünüm';
    const icon = nextIsDark ? '🌙' : '☀️';
    for (const button of document.querySelectorAll('[data-theme-toggle]')) {
      button.setAttribute('aria-label', label);
      button.title = label;
      const iconNode = button.querySelector('.theme-icon');
      const labelNode = button.querySelector('.theme-label');
      if (iconNode) iconNode.textContent = icon;
      if (labelNode) labelNode.textContent = label;
    }
  }

  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    updateButtons(theme);
  }

  function choose(theme) {
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (_) { /* depolama kapalı */ }
    apply(theme);
  }

  apply(savedTheme() || (media.matches ? 'dark' : 'light'));

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-theme-toggle]');
    if (!button) return;
    choose(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });

  document.addEventListener('DOMContentLoaded', () => {
    updateButtons(document.documentElement.dataset.theme);
  });

  media.addEventListener('change', (event) => {
    if (!savedTheme()) apply(event.matches ? 'dark' : 'light');
  });
})();
