(function () {
  'use strict';

  const STORAGE_KEY = 'qyx_prompt_versions';
  const MAX_VERSIONS = 50;

  /**
   * Read all saved prompt versions from localStorage.
   */
  function getVersions() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      return Array.isArray(saved) ? saved : [];
    } catch (error) {
      console.warn('Could not load prompt versions:', error);
      return [];
    }
  }

  /**
   * Save the complete version list to localStorage.
   */
  function storeVersions(versions) {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(versions.slice(0, MAX_VERSIONS))
      );
      return true;
    } catch (error) {
      console.warn('Could not save prompt versions:', error);
      return false;
    }
  }

  /**
   * Create a new version of the editor content.
   */
  function saveVersion(content) {
    const text = String(content || '').trim();

    // Don't save empty versions.
    if (!text) {
      return null;
    }

    const versions = getVersions();

    // Don't create duplicate consecutive versions.
    if (versions.length && versions[0].content === text) {
      return versions[0];
    }

    const newVersion = {
      id: `prompt-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      content: text,
      timestamp: new Date().toISOString(),
      name: '',
      note: ''
    };

    versions.unshift(newVersion);

    if (!storeVersions(versions)) {
      return null;
    }

    return newVersion;
  }
function initAutoSave() {
  const editor = document.getElementById('codeEditor');

  if (!editor) {
    return;
  }

  let saveTimer = null;

  editor.addEventListener('input', () => {
    clearTimeout(saveTimer);

    saveTimer = setTimeout(() => {
      saveVersion(editor.value);
    }, 2000);
  });
}
function initVersionHistoryUI() {
  const historyBtn = document.getElementById('versionHistoryBtn');
  const historyPanel = document.getElementById('versionHistoryPanel');
  const closeBtn = document.getElementById('closeVersionHistoryBtn');
  const historyList = document.getElementById('versionHistoryList');

  if (!historyBtn || !historyPanel || !closeBtn || !historyList) {
    return;
  }

  function renderVersions() {
    const versions = getVersions();

    historyList.innerHTML = '';

    if (versions.length === 0) {
      const emptyMessage = document.createElement('p');
      emptyMessage.textContent = 'No versions saved yet.';
      historyList.appendChild(emptyMessage);
      return;
    }

    versions.forEach((version, index) => {
      const item = document.createElement('div');
      item.className = 'prompt-version-item';

      const title = document.createElement('strong');
      title.textContent = version.name || `Version ${versions.length - index}`;

      const time = document.createElement('small');
      time.textContent = new Date(version.timestamp).toLocaleString();

      const preview = document.createElement('p');
      preview.textContent =
        version.content.length > 80
          ? version.content.slice(0, 80) + '...'
          : version.content;

      item.appendChild(title);
      item.appendChild(document.createElement('br'));
      item.appendChild(time);
      item.appendChild(preview);

      historyList.appendChild(item);
    });
  }

  historyBtn.addEventListener('click', () => {
    renderVersions();
    historyPanel.hidden = false;
  });

  closeBtn.addEventListener('click', () => {
    historyPanel.hidden = true;
  });
}

function init() {
  initAutoSave();
  initVersionHistoryUI();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
  // Expose a small API for the version-history UI.
  window.QyxPromptVersioning = {
    getVersions,
    saveVersion
  };
})();