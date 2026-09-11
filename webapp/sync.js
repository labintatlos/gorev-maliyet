// Bağlantı durumu ve bekleyen kayıtların Telegram sendData ile bota iletilmesi

const Sync = (function () {
  'use strict';

  const MAX_BYTES = 4096; // Telegram sendData sınırı
  const MAX_BATCH = 10; // bot.py WEBAPP_MAX_BATCH ile aynı
  const listeners = [];

  function isOnline() {
    return navigator.onLine !== false;
  }

  function notify() {
    listeners.forEach((listener) => {
      try {
        listener(isOnline());
      } catch (err) {
        console.error(err);
      }
    });
  }

  window.addEventListener('online', notify);
  window.addEventListener('offline', notify);

  function byteLength(value) {
    const text = JSON.stringify(value);
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(text).length;
    return unescape(encodeURIComponent(text)).length;
  }

  function buildBatchPayload(items) {
    return { v: 2, batch: items.map((item) => item.data) };
  }

  // Kuyruğun başından tek gönderime sığan kayıtları seçer.
  function takeSendable(queue) {
    const chosen = [];
    for (const item of queue) {
      if (chosen.length >= MAX_BATCH) break;
      if (byteLength(buildBatchPayload(chosen.concat(item))) > MAX_BYTES) break;
      chosen.push(item);
    }
    return chosen;
  }

  function sendToBot(payload, onFailure) {
    const tg = window.Telegram && window.Telegram.WebApp;
    const fail = (reason) => onFailure && onFailure(reason);
    if (!tg || typeof tg.sendData !== 'function') {
      fail('unsupported');
      return false;
    }
    if (byteLength(payload) > MAX_BYTES) {
      fail('too_large');
      return false;
    }
    try {
      tg.sendData(JSON.stringify(payload));
    } catch (err) {
      fail('error');
      return false;
    }
    // Başarılı sendData Mini App'i kapatır; uygulama hâlâ açıksa gönderim reddedilmiştir.
    setTimeout(() => fail('not_closed'), 2500);
    return true;
  }

  return {
    MAX_BYTES,
    MAX_BATCH,
    isOnline,
    onChange: (listener) => listeners.push(listener),
    byteLength,
    buildBatchPayload,
    takeSendable,
    sendToBot,
  };
})();
