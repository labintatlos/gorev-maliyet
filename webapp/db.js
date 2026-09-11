// localStorage: form taslağı, son gönderilen görev ve çevrimdışı gönderim kuyruğu

const Store = (function () {
  'use strict';

  const KEYS = {
    draft: 'gm_draft_v3',
    legacyDraft: 'last_calc_prefs_v2',
    lastSubmitted: 'gm_last_submitted_v1',
    queue: 'gorev_calculations_pending',
  };

  function read(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (err) {
      return fallback;
    }
  }

  function write(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (err) {
      console.error('Yerel kayıt yazılamadı:', err);
      return false;
    }
  }

  function getQueue() {
    const queue = read(KEYS.queue, []);
    // v3.6 kuyruğunda "synced" işaretli kayıtlar gönderilmiş sayılır.
    return Array.isArray(queue) ? queue.filter((item) => item && item.data && !item.synced) : [];
  }

  return {
    loadDraft() {
      return read(KEYS.draft, null) || read(KEYS.legacyDraft, null);
    },
    saveDraft(draft) {
      return write(KEYS.draft, draft);
    },
    loadLastSubmitted() {
      return read(KEYS.lastSubmitted, null);
    },
    saveLastSubmitted(payload) {
      return write(KEYS.lastSubmitted, payload);
    },
    getQueue,
    enqueue(payload) {
      const queue = getQueue();
      const id = Date.now();
      queue.push({ id, data: payload, timestamp: new Date().toISOString() });
      return write(KEYS.queue, queue) ? id : null;
    },
    removeFromQueue(ids) {
      const remove = new Set(ids);
      return write(KEYS.queue, getQueue().filter((item) => !remove.has(item.id)));
    },
    replaceQueue(queue) {
      return write(KEYS.queue, queue);
    },
    clearQueue() {
      return write(KEYS.queue, []);
    },
  };
})();
