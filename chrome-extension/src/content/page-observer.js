/**
 * Page Observer - Detects LinkedIn SPA navigation with debouncing
 */

let debounceTimer = null;
let lastUrl = window.location.href;

const observer = new MutationObserver(() => {
  // Only fire event when URL actually changes (SPA navigation)
  const currentUrl = window.location.href;
  if (currentUrl === lastUrl) return;
  lastUrl = currentUrl;

  // Debounce: wait 500ms after last mutation before dispatching
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    window.dispatchEvent(new CustomEvent("linkedinPageChanged"));
  }, 500);
});

observer.observe(document.body, {
  childList: true,
  subtree: true,
});
