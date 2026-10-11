(function () {
  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }

  function applyTheme() {
    const isDark = getTheme() === 'dark';
    const darkLink  = document.getElementById('hljs-dark');
    const lightLink = document.getElementById('hljs-light');
    if (darkLink)  darkLink.disabled  = !isDark;
    if (lightLink) lightLink.disabled = isDark;
  }

  function highlightAllCode() {
    if (typeof hljs === 'undefined') return;
    document.querySelectorAll('.issue-snippet pre code, .suggest-example pre code').forEach(block => {
      if (block.dataset.highlighted) return;
      hljs.highlightElement(block);
    });
  }

  // Expose globally so renderDebug / renderSuggest etc. can call it
  window.highlightAllCode = highlightAllCode;

  // Re-apply theme whenever data-theme changes
  const observer = new MutationObserver(applyTheme);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // Run once on load
  applyTheme();
})();