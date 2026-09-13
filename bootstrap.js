/* Only the Python bootstrap and offline installation live here. Game rules and UI are Python. */
document.addEventListener('DOMContentLoaded', () => {
  const reportFailure = () => {
    if (!window.osmReady) {
      document.getElementById('load-error').hidden = false;
      document.getElementById('next-button').textContent = 'Обновите страницу';
    }
  };
  window.addEventListener('error', reportFailure);
  window.setTimeout(reportFailure, 20000);
  // The body's onload invokes Brython once, cooperating with its own auto-start.
  if (!window.osmStandalone && 'serviceWorker' in navigator && window.isSecureContext && location.protocol !== 'file:') {
    navigator.serviceWorker.register('./sw.js').catch(error => console.info('Offline cache unavailable:', error));
  }
});
