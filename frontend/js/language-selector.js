/**
 * Language selector component for settings
 * Provides UI controls to switch between supported languages
 */

(function() {
  const LANGUAGE_NAMES = {
    en: 'English',
    hi: 'हिन्दी (Hindi)'
  };

  function createLanguageSelector() {
    if (typeof i18next === 'undefined') {
      console.warn('i18next not initialized');
      return null;
    }

    const container = document.createElement('div');
    container.className = 'language-selector-container';
    container.innerHTML = `
      <div class="setting-group">
        <label for="language-select" class="setting-label" data-i18n="settings.language">Language</label>
        <select id="language-select" class="language-select">
          ${window.getAvailableLanguages().map(lang =>
            `<option value="${lang}" ${lang === window.getCurrentLanguage() ? 'selected' : ''}>
              ${LANGUAGE_NAMES[lang] || lang}
            </option>`
          ).join('')}
        </select>
        <p class="setting-description" data-i18n="settings.languageDescription">
          Select your preferred language. The interface will update immediately.
        </p>
      </div>
    `;

    const select = container.querySelector('#language-select');
    select.addEventListener('change', (e) => {
      const newLanguage = e.target.value;
      if (window.setLanguage) {
        window.setLanguage(newLanguage);
        console.log(`Language changed to: ${newLanguage}`);
      }
    });

    return container;
  }

  // Expose globally
  window.createLanguageSelector = createLanguageSelector;
  window.LANGUAGE_NAMES = LANGUAGE_NAMES;

  // If there's a settings page with id="language-settings", inject the selector
  window.addEventListener('DOMContentLoaded', () => {
    const settingsContainer = document.getElementById('language-settings');
    if (settingsContainer && typeof i18next !== 'undefined') {
      const selector = createLanguageSelector();
      if (selector) {
        settingsContainer.appendChild(selector);
      }
    }
  });
})();
