/**
 * i18n initialization and configuration
 * Supports English (en) and Hindi (hi) out of the box
 */

(function() {
  const SUPPORTED_LANGUAGES = ['en', 'hi'];
  const DEFAULT_LANGUAGE = 'en';
  const STORAGE_KEY = 'qyx_language';

  async function initializeI18n() {
    if (typeof i18next === 'undefined') {
      console.warn('i18next library not loaded');
      return;
    }

    try {
      // Fetch locale resources
      const resources = {};
      for (const lang of SUPPORTED_LANGUAGES) {
        try {
          const response = await fetch(`locales/${lang}.json`);
          if (response.ok) {
            resources[lang] = { translation: await response.json() };
          }
        } catch (e) {
          console.warn(`Failed to load locale ${lang}:`, e);
        }
      }

      // Initialize i18next
      await i18next.init({
        resources,
        fallbackLng: DEFAULT_LANGUAGE,
        defaultNS: 'translation',
        interpolation: {
          escapeValue: false
        },
        detection: {
          order: ['localStorage', 'navigator'],
          caches: ['localStorage'],
          lookupLocalStorage: STORAGE_KEY
        }
      });

      // Set initial language from storage or browser
      const savedLanguage = localStorage.getItem(STORAGE_KEY);
      const browserLanguage = navigator.language.split('-')[0];
      const languageToUse = savedLanguage ||
                           (SUPPORTED_LANGUAGES.includes(browserLanguage) ? browserLanguage : DEFAULT_LANGUAGE);

      await i18next.changeLanguage(languageToUse);

      // Expose globally
      window.i18n = i18next;
      window.setLanguage = setLanguage;
      window.getAvailableLanguages = () => SUPPORTED_LANGUAGES;
      window.getCurrentLanguage = () => i18next.language;

      // Translate page content if needed
      updatePageTranslations();

      console.log(`i18n initialized with language: ${i18next.language}`);
    } catch (e) {
      console.error('Failed to initialize i18n:', e);
    }
  }

  function setLanguage(lang) {
    if (!SUPPORTED_LANGUAGES.includes(lang)) {
      console.warn(`Language ${lang} not supported`);
      return;
    }

    localStorage.setItem(STORAGE_KEY, lang);
    i18next.changeLanguage(lang);
    updatePageTranslations();
  }

  function updatePageTranslations() {
    // Update page title
    const titleElement = document.querySelector('title');
    if (titleElement) {
      titleElement.textContent = i18next.t('app.title');
    }

    // Update data-i18n attributes
    document.querySelectorAll('[data-i18n]').forEach(element => {
      const key = element.getAttribute('data-i18n');
      const translation = i18next.t(key);

      if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
        element.placeholder = translation;
      } else {
        element.textContent = translation;
      }
    });

    // Update data-i18n-title attributes (for titles/tooltips)
    document.querySelectorAll('[data-i18n-title]').forEach(element => {
      const key = element.getAttribute('data-i18n-title');
      element.title = i18next.t(key);
    });

    // Update data-i18n-aria attributes (for accessibility)
    document.querySelectorAll('[data-i18n-aria]').forEach(element => {
      const key = element.getAttribute('data-i18n-aria');
      element.setAttribute('aria-label', i18next.t(key));
    });
  }

  // Initialize i18n when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeI18n);
  } else {
    initializeI18n();
  }

  // Export helper function for translation
  window.t = function(key) {
    return typeof i18next !== 'undefined' ? i18next.t(key) : key;
  };
})();
