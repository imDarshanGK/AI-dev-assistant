# Internationalization (i18n) Setup Guide

This document explains how to add and manage translations in QyverixAI.

## Current Supported Languages

- **English** (en) - Default language
- **Hindi** (hi) - हिन्दी

## Architecture

The i18n system uses:
- **i18next** - Core translation library
- **Locale JSON files** - Translation strings organized by namespace
- **Language detector** - Automatic language detection based on browser settings
- **Local storage** - Persistent language preference

## File Structure

```
frontend/
├── locales/
│   ├── en.json         # English translations
│   ├── hi.json         # Hindi translations
│   ├── es.json         # (Future) Spanish translations
│   └── zh.json         # (Future) Chinese translations
├── js/
│   ├── i18n-init.js              # i18n initialization and core functions
│   └── language-selector.js       # Language selector UI component
└── INTERNATIONALIZATION.md        # This file
```

## Using Translations in HTML

### Method 1: data-i18n Attributes (Recommended for static content)

```html
<button data-i18n="buttons.submit">Submit</button>
<input type="text" data-i18n="labels.inputCode" placeholder="Enter your code">
```

The i18n system automatically translates elements with `data-i18n` attributes on page load and when language changes.

### Method 2: JavaScript

```javascript
// Get a translation
const translation = t('buttons.submit'); // Returns "Submit" or translated text

// Change language
setLanguage('hi'); // Switches to Hindi

// Get current language
const current = getCurrentLanguage(); // Returns 'en', 'hi', etc.

// Get available languages
const available = getAvailableLanguages(); // Returns ['en', 'hi']
```

### Method 3: i18next Direct Access

```javascript
// After i18n is initialized, access via window.i18n
window.i18n.t('app.title'); // Returns translated title
```

## Adding a New Language

### 1. Create a new locale file

Create `frontend/locales/xx.json` (where `xx` is the language code):

```json
{
  "app": {
    "title": "QyverixAI — [Language Name]",
    "description": "[Description in target language]"
  },
  "navigation": {
    "home": "[Home in target language]",
    "analyze": "[Analyze in target language]"
  }
  // ... copy all keys from en.json and translate values
}
```

### 2. Update SUPPORTED_LANGUAGES

Edit `frontend/js/i18n-init.js`:

```javascript
const SUPPORTED_LANGUAGES = ['en', 'hi', 'xx']; // Add your language code
```

### 3. Update Language Names

Edit `frontend/js/language-selector.js`:

```javascript
const LANGUAGE_NAMES = {
  en: 'English',
  hi: 'हिन्दी (Hindi)',
  xx: 'Language Name' // Add your language
};
```

### 4. Test

- Open the app in a browser with language preference set to `xx`
- Or use the language selector to manually switch
- Verify all `data-i18n` attributes are translated

## Translation Keys Structure

Translations are organized hierarchically:

```
app.*              - Application-wide strings (title, description)
navigation.*       - Navigation menu items
buttons.*          - Button labels
labels.*           - Form labels and field names
messages.*         - User messages (success, error, info)
errors.*           - Error messages
settings.*         - Settings page strings
auth.*             - Authentication pages (login, signup)
shortcuts.*        - Keyboard shortcut hints
```

## Fallback Behavior

- If a translation key is missing, the key itself is displayed (e.g., "app.title")
- If a language is not supported, English (en) is used as fallback
- If i18next fails to load, the page functions in English

## Browser Language Detection

The system automatically detects user language:

1. Checks localStorage for saved preference (`qyx_language`)
2. Checks browser language (`navigator.language`)
3. Falls back to English if no match found

Users can override this in Settings → Language.

## Dynamic Content Translation

For dynamically added elements:

```javascript
// After adding new HTML, call:
updatePageTranslations();

// Or translate specific strings in JavaScript:
const message = t('messages.success'); // Returns translated message
element.textContent = message;
```

## RTL Language Support (Future)

Right-to-left (RTL) language support (Arabic, Hebrew) requires additional CSS work:

```css
html[lang="ar"] {
  direction: rtl;
}
```

This is a separate Level 3 feature. Track it in issue #[TBD].

## Contributing Translations

To contribute a new language:

1. Fork the repository
2. Create `frontend/locales/xx.json` with complete translations
3. Update `i18n-init.js` and `language-selector.js`
4. Create a PR with title: `[Feature] Add {Language} (i18n)`
5. Maintainers will review and merge

## Testing i18n Implementation

```javascript
// In browser console:
window.setLanguage('hi');     // Switch to Hindi
window.t('app.title');         // Test translation
window.getCurrentLanguage();   // Verify current language
window.getAvailableLanguages(); // See all supported languages
```

## Troubleshooting

### Translations not appearing
- Check browser console for errors
- Verify locale file exists at `frontend/locales/xx.json`
- Confirm elements have `data-i18n` attribute
- Reload page after language change

### Missing translations
- Check translation key format (should match keys in locale file)
- Fallback to key name is normal for missing translations
- Add missing key to locale files

### i18next not loading
- Verify CDN URL is accessible
- Check network tab in browser dev tools
- Ensure localStorage is not disabled
