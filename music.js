/* The original AI-composed soundtrack is bundled, including in the offline APK. */
(() => {
  function sync(enabled, playing) {
    const track = document.getElementById('background-music');
    if (!track) return;
    track.volume = 0.26;
    if (!enabled || !playing || document.hidden) {
      track.pause();
      return;
    }
    if (track.paused) {
      const promise = track.play();
      if (promise) promise.catch(() => {
        document.getElementById('sound-button').title = 'Нажмите ♪, чтобы управлять музыкой и звуками';
      });
    }
  }
  window.osmMusic = {sync};
  const stop = () => {
    const track = document.getElementById('background-music');
    if (track) track.pause();
  };
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  window.addEventListener('pagehide', stop);
})();
