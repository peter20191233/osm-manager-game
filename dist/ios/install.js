/* Installation and offline status only; the game itself remains Python. */
document.addEventListener('DOMContentLoaded', async () => {
  const status = document.getElementById('offline-status');
  const help = document.getElementById('install-help');
  const standalone = navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;
  if (standalone) help.hidden = true;
  if (!('serviceWorker' in navigator) || !window.isSecureContext) {
    status.textContent = 'Для сохранения игры откройте её в Safari по защищённой ссылке с сайта.';
    return;
  }
  const watchdog = setTimeout(() => {
    if (status.dataset.ready !== 'true') {
      status.textContent = 'Сохранение пока не завершено. Проверьте интернет и свободное место, затем обновите страницу.';
    }
  }, 30000);
  const report = async () => {
    const registration = await navigator.serviceWorker.ready;
    const worker = registration.active;
    if (!worker) return;
    const channel = new MessageChannel();
    const timeout = setTimeout(() => {
      status.textContent = 'Не удалось проверить сохранение. Откройте игру ещё раз с интернетом.';
    }, 10000);
    channel.port1.onmessage = event => {
      clearTimeout(timeout);
      channel.port1.close();
      if (event.data && event.data.offlineReady) {
        clearTimeout(watchdog);
        status.textContent = 'Игра сохранена · можно играть без интернета';
        status.dataset.ready = 'true';
      } else {
        status.textContent = 'Игра ещё не сохранена. Обновите страницу с включённым интернетом.';
      }
    };
    worker.postMessage({type: 'CHECK_OFFLINE'}, [channel.port2]);
  };
  try {
    await navigator.serviceWorker.register('./sw.js', {updateViaCache: 'none'});
    navigator.serviceWorker.addEventListener('controllerchange', report);
    await report();
  } catch (_) {
    clearTimeout(watchdog);
    status.textContent = 'Не удалось сохранить игру. Проверьте интернет и обновите страницу.';
  }
});
