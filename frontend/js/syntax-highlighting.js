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
    document.querySelectorAll('pre code').forEach(block => {
      if (block.dataset.highlighted) return;
      hljs.highlightElement(block);
    });
  }

  function renderMarkdownWithSyntaxHighlight(markdown) {
    if (typeof marked === 'undefined' || typeof hljs === 'undefined') {
      return markdown;
    }

    const renderer = new marked.Renderer();
    renderer.code = function(code, language) {
      const validLanguage = language && hljs.getLanguage(language) ? language : 'plaintext';
      const highlighted = hljs.highlight(code, { language: validLanguage }).value;
      return `<pre><code class="language-${validLanguage} hljs">${highlighted}</code></pre>`;
    };

    try {
      return marked.parse(markdown, { renderer });
    } catch (e) {
      console.warn('Markdown parsing failed:', e);
      return markdown;
    }
  }

  window.highlightAllCode = highlightAllCode;
  window.renderMarkdownWithSyntaxHighlight = renderMarkdownWithSyntaxHighlight;

  const observer = new MutationObserver(applyTheme);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  applyTheme();
})();