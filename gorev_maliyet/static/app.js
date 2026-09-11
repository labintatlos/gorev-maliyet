'use strict';

(() => {
  // KeenDNS bulut tüneli http:// isteğini de siteye iletir ve sunucuya hangi
  // şemayla gelindiğini bildirmez; bu yüzden yönlendirmeyi tarayıcı yapar.
  // Ev ağındaki IP/.local adresleri ve Home Assistant paneli (çerçeve) hariç.
  const host = location.hostname;
  const localHost = host === 'localhost' || host.endsWith('.local') || !host.includes('.') || /^[\d.]+$|:/.test(host);
  if (location.protocol === 'http:' && window.top === window.self && !localHost) {
    location.replace(`https://${location.host}${location.pathname}${location.search}${location.hash}`);
    return;
  }

  const C = window.GorevCalc;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Dinamik içerik yalnızca textContent ile yazılır. Sunucu satır içi stile izin
  // vermediği için (CSP) genişlik gibi değerler CSSOM üzerinden verilir.
  function h(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (value === undefined || value === null || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'dataset') Object.assign(node.dataset, value);
      else if (key === 'style') {
        for (const [prop, val] of Object.entries(value)) {
          if (prop.startsWith('--')) node.style.setProperty(prop, val);
          else node.style[prop] = val;
        }
      } else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : String(value));
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : String(child));
    }
    return node;
  }

  const MAX_DUTIES = 12;
  const DEFAULT_DUTY = { departure: '09:35', arrival: '19:25', fuel_liters: 750 };
  const FUEL_LABELS = { diesel: 'Dizel', gasoline: 'Benzin' };
  const PRICE_LABELS = { diesel: 'motorin', gasoline: 'benzin' };
  const NUDGES = [-60, -15, -5, 5, 15, 60];
  const PAGES = ['hesapla', 'gecmis', 'istatistik', 'ayarlar', 'yonetim'];
  const POSITION_NAMES = { subay: 'Subay', astsubay: 'Astsubay', uzman: 'Uzman', memur: 'Memur' };
  const ACTIVITY_LABELS = {
    setup: 'İlk kurulumu yaptı',
    login: 'Giriş yaptı',
    logout: 'Çıkış yaptı',
    registration: 'Üyelik başvurusu yaptı',
    password_reset_request: 'Şifre yenileme talep etti',
    password_change: 'Şifresini değiştirdi',
    calculation: 'Hesaplama yaptı',
    settings: 'Sabit ayarları değiştirdi',
    market_refresh: 'Piyasa verisini yeniledi',
    history_delete: 'Kayıt sildi',
    history_clear: 'Geçmişini temizledi',
    export: 'CSV indirdi',
    issue_report: 'Sorun bildirdi',
    issue_resolve: 'Bildirim kapattı',
    person_create: 'Kişi ekledi',
    person_update: 'Kişiyi güncelledi',
  };

  const pad = (value) => String(value).padStart(2, '0');
  const todayISO = (date = new Date()) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const minutesOfDay = (date) => date.getHours() * 60 + date.getMinutes();
  const money = (value, decimals = 2) => `₺${C.formatMoney(value, decimals)}`;
  const share = (part, whole) => (whole > 0 ? (part / whole) * 100 : 0);
  const clockDuration = (minutes) => `${Math.floor(minutes / 60)}:${pad(minutes % 60)}`;

  function formatDateTR(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    return match ? `${match[3]}.${match[2]}.${match[1]}` : '—';
  }

  function formatDateTimeTR(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || '');
    return match ? `${match[3]}.${match[2]}.${match[1]} ${match[4]}:${match[5]}` : '—';
  }

  const ui = {
    boot: $('#boot'), auth: $('#auth'), app: $('#app'),
    authTabs: $('#auth-tabs'), loginForm: $('#login-form'), registerForm: $('#register-form'),
    resetForm: $('#reset-form'), setupForm: $('#setup-form'), ingressNote: $('#ingress-note'),
    accountBtn: $('#account-btn'), accountMenu: $('#account-menu'),
    busy: $('#busy'), busyText: $('#busy-text'), toast: $('#toast'),
    passwordDialog: $('#password-dialog'), passwordForm: $('#password-form'),
    issueDialog: $('#issue-dialog'), issueForm: $('#issue-form'),
    peopleDialog: $('#people-dialog'), peopleList: $('#people-list'), personForm: $('#person-form'),
    recordDialog: $('#record-dialog'), settingsForm: $('#settings-form'), duties: $('#duties'),
  };

  let session = null;
  let boot = null;
  let busy = false;
  let historyPage = 0;
  let recordState = null;

  const form = { dutyDate: todayISO(), fuelType: 'diesel', personnel: 4, duties: [], nextId: 1 };

  // ── Sunucu ─────────────────────────────────────────────────────────────
  // Adresler göreli yazılır: site hem kök dizinde (KeenDNS) hem de Home
  // Assistant panelinin /api/hassio_ingress/... önekinin altında açılır.
  async function api(method, path, body) {
    let response;
    try {
      response = await fetch(path, {
        method,
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'GorevMaliyet' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (_) {
      const error = new Error('Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edin.');
      error.network = true;
      throw error;
    }
    let data = null;
    try { data = await response.json(); } catch (_) { /* boş yanıt */ }
    if (!response.ok) {
      const error = new Error((data && data.error) || `Sunucuya ulaşılamadı (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  async function handleError(error) {
    if (error.status === 401) { await start(); return; }
    toast(error.message, 'error');
  }

  // ── Bekleme ve bildirim ────────────────────────────────────────────────
  let busyTimer = null;
  function setBusy(on, text) {
    busy = on;
    clearTimeout(busyTimer);
    if (on) {
      ui.busyText.textContent = text || 'Yükleniyor…';
      busyTimer = setTimeout(() => { ui.busy.hidden = false; }, 300);
    } else {
      ui.busy.hidden = true;
    }
  }

  let toastTimer = null;
  function toast(message, kind) {
    ui.toast.textContent = message;
    ui.toast.className = `toast ${kind || ''}`.trim();
    ui.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { ui.toast.hidden = true; }, Math.max(3500, message.length * 60));
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      const area = h('textarea', { readonly: true });
      area.value = text;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.append(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (__) { ok = false; }
      area.remove();
      return ok;
    }
  }

  function storageGet(key) {
    try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (_) { return null; }
  }

  function storageSet(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (_) { return false; }
  }

  // ── Giriş ──────────────────────────────────────────────────────────────
  function formError(target, message) {
    const node = $('.form-error', target);
    node.textContent = message || '';
    node.hidden = !message;
  }

  function formData(target) {
    const data = {};
    for (const field of target.elements) {
      if (!field.name) continue;
      data[field.name] = field.type === 'checkbox' ? field.checked : field.value;
    }
    return data;
  }

  async function submitForm(target, path, after) {
    const submit = $('button[type=submit]', target);
    formError(target, '');
    submit.disabled = true;
    try {
      await api('POST', path, formData(target));
      await after();
    } catch (error) {
      formError(target, error.message);
    } finally {
      submit.disabled = false;
    }
  }

  function showAuthView(view) {
    ui.loginForm.hidden = view !== 'login';
    ui.registerForm.hidden = view !== 'register';
    ui.resetForm.hidden = view !== 'reset';
    for (const tab of ui.authTabs.querySelectorAll('[data-auth-view]')) {
      const active = tab.dataset.authView === view;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    }
    ui.ingressNote.hidden = view !== 'login' || !session.ingress;
    const first = $('input', view === 'login' ? ui.loginForm : view === 'register' ? ui.registerForm : ui.resetForm);
    setTimeout(() => first.focus(), 30);
  }

  function showAuth() {
    boot = null;
    ui.app.hidden = true;
    ui.auth.hidden = false;
    ui.setupForm.hidden = !session.setup_required;
    ui.authTabs.hidden = session.setup_required;
    if (session.setup_required) {
      ui.loginForm.hidden = true;
      ui.registerForm.hidden = true;
      ui.resetForm.hidden = true;
      setTimeout(() => $('input', ui.setupForm).focus(), 30);
    } else {
      showAuthView('login');
    }
  }

  async function start() {
    try {
      session = await api('GET', 'api/session');
    } catch (_) {
      ui.boot.hidden = false;
      ui.boot.textContent = 'Sunucuya ulaşılamadı. Sayfayı yenileyin.';
      return;
    }
    ui.boot.hidden = true;
    if (!session.user) { showAuth(); return; }
    try {
      await showApp();
    } catch (error) {
      if (error.status === 401) { session.user = null; showAuth(); } else toast(error.message, 'error');
    }
  }

  async function showApp() {
    boot = await api('GET', 'api/bootstrap');
    const user = boot.user;
    ui.auth.hidden = true;
    ui.app.hidden = false;
    $('#account-name').textContent = user.display_name;
    $('#account-username').textContent = `@${user.username}${user.is_admin ? ' · yönetici' : ''}`;
    $('#account-initial').textContent = (user.display_name.trim()[0] || '•').toLocaleUpperCase('tr');
    $('[data-cmd=people]', ui.accountMenu).hidden = !user.is_admin;
    $('[data-cmd=logout]', ui.accountMenu).hidden = user.via === 'ingress';
    $('#tabs [data-page=yonetim]').hidden = !user.is_admin;

    fillSettings();
    renderConstants();
    if (!applySnapshot(storageGet(draftKey()))) applySnapshot({ personnel: 4, fuel_type: 'diesel', duties: [DEFAULT_DUTY] });
    form.dutyDate = todayISO();
    syncStaticInputs();
    renderMarket();
    renderNet();
    renderDuties();
    renderQueue();
    showCalcView();
    route();
  }

  async function logout() {
    try { await api('POST', 'api/logout', {}); } catch (_) { /* yine de çık */ }
    await start();
  }

  // ── Sayfalar ───────────────────────────────────────────────────────────
  function route() {
    if (!boot) return;
    let page = location.hash.replace('#', '') || 'hesapla';
    if (!PAGES.includes(page) || (page === 'yonetim' && !boot.user.is_admin)) page = 'hesapla';
    for (const section of $$('.page')) section.hidden = section.dataset.page !== page;
    for (const tab of $$('#tabs a')) {
      const active = tab.dataset.page === page;
      tab.classList.toggle('active', active);
      if (active) tab.setAttribute('aria-current', 'page');
      else tab.removeAttribute('aria-current');
    }
    if (page === 'gecmis') loadHistory(historyPage);
    if (page === 'istatistik') loadStats();
    if (page === 'yonetim') loadAdmin();
    window.scrollTo({ top: 0 });
  }

  // ── Piyasa verisi ──────────────────────────────────────────────────────
  const market = () => boot.market;
  const fuelPrice = () => (form.fuelType === 'gasoline' ? market().gasoline : market().diesel);
  const hasPricing = () => Boolean(boot) && market().eur !== null && market().monthly_salary !== null && fuelPrice() !== null;
  const hasSun = () => Boolean(boot && market().sunrise && market().sunset);

  function dataRow(label, value, sub) {
    return h('div', null, h('dt', { text: label }), h('dd', null, value, sub ? h('small', { text: sub }) : null));
  }

  function renderMarket() {
    const m = market();
    $('#mk-eur').textContent = m.eur !== null ? money(m.eur, 4) : '—';
    $('#mk-eur-date').textContent = m.eur_date ? `TCMB · ${m.eur_date}` : 'TCMB döviz satış';
    $('#mk-fuel-label').textContent = form.fuelType === 'gasoline' ? 'Benzin' : 'Motorin';
    $('#mk-fuel').textContent = fuelPrice() !== null ? `${money(fuelPrice())}/L` : '—';
    $('#mk-fuel-place').textContent = `${m.fuel_province} · Petrol Ofisi`;
    $('#mk-salary').textContent = money(m.monthly_salary, 0);
    $('#mk-sun').textContent = hasSun() ? `${m.sunrise}–${m.sunset}` : '—';
    $('#mk-sun-place').textContent = `${m.solar_province} · bugün`;

    let notice = '';
    if (!m.ready) {
      notice = 'Euro kuru veya akaryakıt fiyatı henüz alınamadı. Hesaplama sırasında yeniden denenecek; Ayarlar → Otomatik veriler bölümünden de yenileyebilirsiniz.';
    } else if (m.last_refresh_at) {
      const days = Math.floor((Date.now() - Date.parse(m.last_refresh_at)) / 86400000);
      if (days >= 2) notice = `Piyasa verileri ${days} gündür güncellenemedi; son başarılı değerler kullanılıyor.`;
    }
    $('#calc-notice-text').textContent = notice;
    $('#calc-notice').hidden = !notice;

    const status = $('#market-status');
    status.textContent = m.ready ? 'Hesaplamaya hazır' : 'Veri eksik';
    status.className = m.ready ? 'badge' : 'badge warning';
    $('#market-list').replaceChildren(
      dataRow('Euro · TCMB döviz satış', m.eur !== null ? money(m.eur, 4) : 'alınamadı', m.eur_date || ''),
      dataRow(`${m.fuel_province} motorin`, m.diesel !== null ? `${money(m.diesel)}/L` : 'alınamadı',
        m.fuel_date ? `Petrol Ofisi · ${formatDateTR(m.fuel_date)}` : 'Petrol Ofisi'),
      dataRow(`${m.fuel_province} benzin`, m.gasoline !== null ? `${money(m.gasoline)}/L` : 'alınamadı'),
      dataRow(`${m.solar_province} gün doğumu / batımı`, hasSun() ? `${m.sunrise} / ${m.sunset}` : '—', 'bugün'),
      dataRow('Son kontrol', m.last_refresh_at ? formatDateTimeTR(m.last_refresh_at) : 'Henüz yok'),
    );
  }

  function renderConstants() {
    const k = boot.constants;
    $('#constants-list').replaceChildren(
      dataRow('Günlük amortisman', `€${C.formatMoney(k.daily_amortization_eur)}`),
      dataRow('Saatlik amortisman', `€${C.formatMoney(k.hourly_amortization_eur, 4)}`),
      dataRow('Dizel dönüşümü', `1 L = ${C.formatMoney(k.density.diesel, 3)} kg`),
      dataRow('Benzin dönüşümü', `1 L = ${C.formatMoney(k.density.gasoline, 3)} kg`),
      dataRow('Saatlik maaş', `Aylık maaş / ${k.hours_per_month}`),
      dataRow('Gece yarısı geçişi', 'MOD(Aborda − Avara, 1)'),
    );
  }

  function fillSettings() {
    for (const select of [$('#set-fuel'), $('#set-solar')]) {
      select.replaceChildren(...boot.provinces.map((name) => h('option', { value: name, text: name })));
    }
    $('#set-fuel').value = boot.settings.fuel_province;
    $('#set-solar').value = boot.settings.solar_province;
    $('#set-salary').value = C.formatNumber(boot.settings.monthly_salary, 2);
  }

  function pollMarket(tries) {
    setTimeout(async () => {
      try {
        const { market: fresh } = await api('GET', 'api/market');
        boot.market = fresh;
        renderMarket();
        renderDuties();
        if (fresh.diesel === null && tries > 1) pollMarket(tries - 1);
      } catch (_) { /* sonraki açılışta güncellenir */ }
    }, 4000);
  }

  // ── Hesaplama formu ────────────────────────────────────────────────────
  const draftKey = () => `gm_draft_${boot.user.id}`;
  const queueKey = () => `gm_queue_${boot.user.id}`;

  function sanitizeFuel(value) {
    const n = Number(String(value).replace(',', '.'));
    return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) / 100 : 0;
  }

  function sanitizePersonnel(value) {
    const n = parseInt(value, 10);
    return Number.isFinite(n) ? Math.min(500, Math.max(1, n)) : 4;
  }

  function makeDuty(values = {}) {
    return {
      id: form.nextId++,
      departure: C.sanitizeTime(values.departure, DEFAULT_DUTY.departure),
      arrival: C.sanitizeTime(values.arrival, DEFAULT_DUTY.arrival),
      fuel_liters: values.fuel_liters == null ? DEFAULT_DUTY.fuel_liters : sanitizeFuel(values.fuel_liters),
    };
  }

  function applySnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return false;
    form.personnel = sanitizePersonnel(snapshot.personnel);
    form.fuelType = snapshot.fuel_type === 'gasoline' ? 'gasoline' : 'diesel';
    const list = Array.isArray(snapshot.duties) ? snapshot.duties.slice(0, MAX_DUTIES) : [];
    form.nextId = 1;
    form.duties = list.length ? list.map(makeDuty) : [makeDuty(DEFAULT_DUTY)];
    return true;
  }

  function snapshot() {
    return {
      personnel: form.personnel,
      fuel_type: form.fuelType,
      duties: form.duties.map(({ departure, arrival, fuel_liters }) => ({ departure, arrival, fuel_liters })),
    };
  }

  const saveDraft = () => { if (boot) storageSet(draftKey(), snapshot()); };
  const findDuty = (id) => form.duties.find((duty) => String(duty.id) === String(id));

  function dutyMetrics(duty) {
    const minutes = C.durationMinutes(duty.departure, duty.arrival);
    const m = market();
    return {
      minutes,
      kg: duty.fuel_liters * C.DENSITY[form.fuelType],
      light: hasSun() ? C.splitDaylight(duty.departure, duty.arrival, m.sunrise, m.sunset) : null,
      cost: hasPricing()
        ? C.calculate({
          minutes,
          eur: m.eur,
          salary: m.monthly_salary,
          personnel: form.personnel,
          liters: duty.fuel_liters,
          price: fuelPrice(),
          fuelType: form.fuelType,
          dailyAmortEur: boot.constants.daily_amortization_eur,
        })
        : null,
    };
  }

  function totals() {
    const sum = { minutes: 0, liters: 0, day: 0, night: 0, amortization: 0, personnelCost: 0, fuelCost: 0, total: 0 };
    for (const duty of form.duties) {
      const metrics = dutyMetrics(duty);
      sum.minutes += metrics.minutes;
      sum.liters += duty.fuel_liters;
      if (metrics.light) {
        sum.day += metrics.light.day;
        sum.night += metrics.light.night;
      }
      if (metrics.cost) {
        sum.amortization += metrics.cost.amortization;
        sum.personnelCost += metrics.cost.personnelCost;
        sum.fuelCost += metrics.cost.fuelCost;
        sum.total += metrics.cost.total;
      }
    }
    return sum;
  }

  function nudgeLabel(delta) {
    const sign = delta < 0 ? '−' : '+';
    return Math.abs(delta) === 60 ? `${sign}1 sa` : `${sign}${Math.abs(delta)}`;
  }

  function timeBox(field, icon, label) {
    return h('div', { class: 'time-box' },
      h('div', { class: 'time-box-head' },
        h('span', { text: `${icon} ${label}` }),
        h('button', { type: 'button', class: 'link-btn', dataset: { action: 'now', field }, text: 'Şimdi' })),
      h('input', { type: 'time', class: 'time-input num', dataset: { field }, 'aria-label': `${label} saati` }),
      h('div', { class: 'nudge' },
        NUDGES.map((delta) => h('button', { type: 'button', dataset: { action: 'nudge', field, delta: String(delta) }, text: nudgeLabel(delta) }))));
  }

  function dutyCard(duty, index) {
    const m = market();
    const sun = hasSun()
      ? { '--sr': `${((C.parseTime(m.sunrise) / C.DAY_MINUTES) * 100).toFixed(2)}%`, '--ss': `${((C.parseTime(m.sunset) / C.DAY_MINUTES) * 100).toFixed(2)}%` }
      : null;
    return h('article', { class: 'card duty', dataset: { id: String(duty.id) } },
      h('header', { class: 'duty-head' },
        h('div', { class: 'duty-title' }, h('span', { class: 'duty-num num', text: String(index + 1) }), 'Görev'),
        h('div', { class: 'duty-actions' },
          h('span', { class: 'badge num', dataset: { role: 'duration' } }),
          form.duties.length > 1
            ? h('button', { type: 'button', class: 'icon-btn', dataset: { action: 'remove' }, 'aria-label': `${index + 1}. görevi sil`, text: '✕' })
            : null)),
      h('div', { class: 'grid-2' }, timeBox('departure', '🚀', 'Avara'), timeBox('arrival', '⚓', 'Aborda')),
      h('div', { class: 'timeline', 'aria-hidden': 'true' },
        h('div', { class: sun ? 'tl-track' : 'tl-track no-sun', style: sun }, h('div', { dataset: { role: 'segments' } })),
        h('div', { class: 'tl-scale' }, ['00', '06', '12', '18', '24'].map((label, i) => h('span', { text: label, style: { left: `${i * 25}%` } })))),
      h('div', { class: 'fuel-row' },
        h('div', null,
          h('span', { class: 'field-label', text: 'Harcanan yakıt' }),
          h('small', { class: 'hint num', dataset: { role: 'kg' } })),
        h('div', { class: 'stepper wide' },
          h('button', { type: 'button', dataset: { action: 'fuel', delta: '-5' }, 'aria-label': '5 litre azalt', text: '−' }),
          h('input', { type: 'number', class: 'num', dataset: { field: 'fuel_liters' }, inputmode: 'decimal', min: '0', step: 'any', 'aria-label': 'Yakıt litresi' }),
          h('span', { class: 'unit', text: 'L' }),
          h('button', { type: 'button', dataset: { action: 'fuel', delta: '5' }, 'aria-label': '5 litre artır', text: '+' }))),
      h('div', { class: 'pill-row' },
        [-50, -15, 15, 50].map((delta) => h('button', { type: 'button', class: 'pill', dataset: { action: 'fuel', delta: String(delta) }, text: `${delta < 0 ? '−' : '+'}${Math.abs(delta)} L` }))),
      h('footer', { class: 'duty-foot', dataset: { role: 'foot' } },
        h('span', { class: 'hint num', dataset: { role: 'light' } }),
        h('strong', { class: 'num', dataset: { role: 'cost' } })));
  }

  function renderDuties(options = {}) {
    ui.duties.replaceChildren(...form.duties.map(dutyCard));
    if (options.animateId) {
      const card = $(`.duty[data-id="${options.animateId}"]`);
      if (card) card.classList.add('enter');
    }
    form.duties.forEach(refreshDuty);
    refreshSummary();
  }

  function refreshDuty(duty) {
    const card = $(`.duty[data-id="${duty.id}"]`);
    if (!card) return;
    const metrics = dutyMetrics(duty);

    for (const input of $$('[data-field]', card)) {
      if (input.tagName !== 'INPUT' || document.activeElement === input) continue;
      input.value = input.dataset.field === 'fuel_liters' ? String(duty.fuel_liters) : duty[input.dataset.field];
    }
    card.classList.toggle('is-invalid', metrics.minutes === 0);
    $('[data-role="duration"]', card).textContent = metrics.minutes === 0 ? 'Süre 0' : C.formatDuration(metrics.minutes);
    $('[data-role="kg"]', card).textContent = `≈ ${C.formatNumber(metrics.kg, 0)} kg ${FUEL_LABELS[form.fuelType].toLocaleLowerCase('tr')}`;

    const start = C.parseTime(duty.departure);
    const segments = [];
    if (start !== null && metrics.minutes > 0) {
      const end = start + metrics.minutes;
      segments.push([start, Math.min(end, C.DAY_MINUTES)]);
      if (end > C.DAY_MINUTES) segments.push([0, end - C.DAY_MINUTES]);
    }
    const pct = (value) => `${((value / C.DAY_MINUTES) * 100).toFixed(3)}%`;
    $('[data-role="segments"]', card).replaceChildren(
      ...segments.map(([from, to]) => h('span', { class: 'tl-seg', style: { left: pct(from), width: pct(to - from) } })));

    $('[data-role="light"]', card).textContent = metrics.light
      ? `☀️ ${C.formatDuration(metrics.light.day)} · 🌙 ${C.formatDuration(metrics.light.night)}`
      : '';
    $('[data-role="cost"]', card).textContent = metrics.cost ? `≈ ${money(metrics.cost.total)}` : '';
    $('[data-role="foot"]', card).hidden = !metrics.light && !metrics.cost;
  }

  function commitDuty(duty) {
    refreshDuty(duty);
    refreshSummary();
    saveDraft();
  }

  function addDuty() {
    if (form.duties.length >= MAX_DUTIES) {
      toast(`Tek seferde en fazla ${MAX_DUTIES} görev hesaplanabilir.`, 'warn');
      return;
    }
    const last = form.duties[form.duties.length - 1];
    const departure = last ? last.arrival : '12:00';
    const duty = makeDuty({ departure, arrival: C.formatTime(C.parseTime(departure) + 120), fuel_liters: 250 });
    form.duties.push(duty);
    renderDuties({ animateId: duty.id });
    saveDraft();
    const card = $(`.duty[data-id="${duty.id}"]`);
    if (card) card.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  function removeDuty(id) {
    if (form.duties.length <= 1) return;
    form.duties = form.duties.filter((duty) => String(duty.id) !== String(id));
    saveDraft();
    const card = $(`.duty[data-id="${id}"]`);
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      renderDuties();
    };
    if (card && !reducedMotion()) {
      card.classList.add('leave');
      card.addEventListener('animationend', finish, { once: true });
      setTimeout(finish, 350);
    } else {
      finish();
    }
  }

  function flagDuty(id) {
    const card = $(`.duty[data-id="${id}"]`);
    if (!card) return;
    card.classList.remove('shake');
    void card.offsetWidth; // animasyonu yeniden başlat
    card.classList.add('shake');
    card.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  function refreshSummary() {
    if (!boot) return;
    const sum = totals();
    const priced = hasPricing();
    const m = market();

    $('#sum-label').textContent = priced ? 'Tahmini toplam maliyet' : 'Toplam görev süresi';
    $('#sum-count').textContent = `${form.duties.length} görev`;
    $('#sum-total').textContent = priced ? money(sum.total) : C.formatDuration(sum.minutes);
    $('#sum-priced').hidden = !priced;
    if (priced) {
      for (const [key, value] of [['amort', sum.amortization], ['pers', sum.personnelCost], ['fuel', sum.fuelCost]]) {
        const part = share(value, sum.total);
        $(`#bar-${key}`).style.width = `${part}%`;
        $(`#lg-${key}`).textContent = money(value);
        $(`#pc-${key}`).textContent = `%${C.formatNumber(part, 1)}`;
      }
    }

    const hours = sum.minutes / 60;
    $('#st-duration').textContent = C.formatDuration(sum.minutes);
    $('#st-fuel').textContent = `${C.formatNumber(sum.liters)} L`;
    if (priced) {
      $('#st-3-label').textContent = 'Saatlik ortalama';
      $('#st-3').textContent = hours > 0 ? money(sum.total / hours, 0) : '—';
    } else {
      $('#st-3-label').textContent = 'Personel';
      $('#st-3').textContent = `${form.personnel} kişi`;
    }
    if (hasSun()) {
      $('#st-4-label').textContent = 'Gündüz / gece';
      $('#st-4').textContent = `☀️ ${clockDuration(sum.day)} · 🌙 ${clockDuration(sum.night)}`;
    } else {
      $('#st-4-label').textContent = 'Yakıt verimi';
      $('#st-4').textContent = hours > 0 ? `${C.formatNumber(sum.liters / hours, 1)} L/sa` : '—';
    }
    $('#sum-note').textContent = priced
      ? `${m.fuel_province} ${PRICE_LABELS[form.fuelType]} ${money(fuelPrice())}/L · Euro ${money(m.eur, 4)} · ${form.personnel} kişi. Kesin tutar kaydederken güncel verilerle hesaplanır.`
      : 'Piyasa verisi eksik olduğu için maliyet önizlemesi gösterilemiyor; kaydederken sunucu verileri yeniden dener.';
    $('#btn-submit').textContent = priced ? `✅ Hesapla ve kaydet · ${money(sum.total, 0)}` : '✅ Hesapla ve kaydet';

    for (const pill of $$('#personnel-presets .pill')) {
      pill.classList.toggle('active', Number(pill.dataset.personnel) === form.personnel);
    }
  }

  function syncStaticInputs() {
    $('#duty-date').value = form.dutyDate;
    $('#personnel').value = String(form.personnel);
    const radio = $(`input[name="fuel_type"][value="${form.fuelType}"]`);
    if (radio) radio.checked = true;
  }

  function setPersonnel(value) {
    form.personnel = sanitizePersonnel(value);
    if (document.activeElement !== $('#personnel')) $('#personnel').value = String(form.personnel);
    form.duties.forEach(refreshDuty);
    refreshSummary();
    saveDraft();
  }

  function applyPreset(kind) {
    if (kind === 'last') {
      if (!boot.last_inputs) { toast('Henüz kayıtlı hesaplama yok.', 'warn'); return; }
      applySnapshot(boot.last_inputs);
      toast('Son hesaplamanın değerleri yüklendi.');
    } else if (kind === 'recent') {
      const now = new Date();
      const fuel = form.duties[0] ? form.duties[0].fuel_liters : 500;
      form.nextId = 1;
      form.duties = [makeDuty({ departure: C.formatTime(minutesOfDay(now) - 240), arrival: C.formatTime(minutesOfDay(now)), fuel_liters: fuel })];
    } else if (kind === 'sample') {
      applySnapshot({ personnel: 4, fuel_type: 'diesel', duties: [DEFAULT_DUTY] });
    }
    form.dutyDate = todayISO();
    syncStaticInputs();
    renderMarket();
    renderDuties();
    saveDraft();
  }

  function validate() {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.dutyDate)) return { message: 'Görev tarihini seçin.' };
    for (let i = 0; i < form.duties.length; i += 1) {
      const duty = form.duties[i];
      if (C.parseTime(duty.departure) === null || C.parseTime(duty.arrival) === null) {
        return { message: `${i + 1}. görev için Avara ve Aborda saatlerini girin.`, id: duty.id };
      }
      if (C.durationMinutes(duty.departure, duty.arrival) === 0) {
        return { message: `${i + 1}. görevde Avara ve Aborda saatleri aynı. Görev süresi 0 olamaz.`, id: duty.id };
      }
    }
    return null;
  }

  function buildPayload() {
    return { duty_date: form.dutyDate, ...snapshot() };
  }

  async function submit() {
    if (busy || !boot) return;
    const error = validate();
    if (error) {
      if (error.id) flagDuty(error.id);
      toast(error.message, 'error');
      return;
    }
    const payload = buildPayload();
    saveDraft();
    if (navigator.onLine === false) { enqueue(payload); return; }
    setBusy(true, 'Hesaplanıyor ve kaydediliyor…');
    try {
      const result = await api('POST', 'api/calculate', payload);
      boot.last_inputs = payload;
      showResult(result);
    } catch (err) {
      if (err.network) enqueue(payload);
      else await handleError(err);
    } finally {
      setBusy(false);
    }
  }

  function summaryText() {
    const sum = totals();
    const lines = [
      '📋 Görev Özeti',
      `📅 ${formatDateTR(form.dutyDate)} · 👥 ${form.personnel} kişi · 🛢 ${FUEL_LABELS[form.fuelType]}`,
      '',
    ];
    form.duties.forEach((duty, index) => {
      const metrics = dutyMetrics(duty);
      const cost = metrics.cost ? ` · ≈ ${money(metrics.cost.total)}` : '';
      lines.push(`${index + 1}. Görev: ${duty.departure}–${duty.arrival} (${C.formatDuration(metrics.minutes)}) · ${C.formatNumber(duty.fuel_liters)} L${cost}`);
    });
    lines.push('', `⏱ Toplam süre: ${C.formatDuration(sum.minutes)} · ⛽ ${C.formatNumber(sum.liters)} L`);
    if (hasPricing()) lines.push(`💰 Tahmini toplam: ${money(sum.total)}`);
    return lines.join('\n');
  }

  // ── Çevrimdışı kuyruk ──────────────────────────────────────────────────
  function getQueue() {
    const queue = storageGet(queueKey());
    return Array.isArray(queue) ? queue.filter((item) => item && item.data) : [];
  }

  function enqueue(payload) {
    const queue = getQueue();
    queue.push({ id: Date.now(), saved_at: new Date().toISOString(), data: payload });
    if (storageSet(queueKey(), queue)) {
      toast('İnternet bağlantısı yok. Hesaplama bu cihazda bekletiliyor; bağlantı gelince “Şimdi gönder” ile kaydedin.', 'warn');
    } else {
      toast('Bağlantı yok ve cihaz depolaması kullanılamıyor; hesaplama kaydedilemedi.', 'error');
    }
    renderQueue();
  }

  function renderQueue() {
    if (!boot) return;
    const queue = getQueue();
    $('#queue-card').hidden = queue.length === 0;
    if (!queue.length) return;
    const online = navigator.onLine !== false;
    $('#queue-count').textContent = String(queue.length);
    $('#queue-hint').textContent = online ? 'Bağlantı var — kayıtları şimdi gönderebilirsiniz.' : 'Bağlantı bekleniyor. Kayıtlar bu cihazda saklanıyor.';
    $('[data-queue="send"]').disabled = !online;
    $('#queue-list').replaceChildren(...queue.map((item) => h('li', null,
      h('div', null,
        h('b', { text: `${formatDateTR(item.data.duty_date)} · ${(item.data.duties || []).length} görev · ${item.data.personnel} kişi` }),
        h('small', { text: `Bekletildi: ${formatDateTimeTR(item.saved_at)}` })),
      h('button', {
        type: 'button', class: 'icon-btn', 'aria-label': 'Kaydı sil', text: '✕',
        onclick: () => { storageSet(queueKey(), getQueue().filter((q) => q.id !== item.id)); renderQueue(); },
      }))));
  }

  async function sendQueue() {
    if (busy) return;
    const queue = getQueue();
    if (!queue.length) return;
    setBusy(true, 'Bekleyen hesaplamalar gönderiliyor…');
    let sent = 0;
    let lastResult = null;
    try {
      for (const item of queue) {
        try {
          lastResult = await api('POST', 'api/calculate', item.data);
          sent += 1;
          storageSet(queueKey(), getQueue().filter((q) => q.id !== item.id));
        } catch (err) {
          if (err.status === 401) { await start(); return; }
          toast(err.network ? 'Bağlantı hâlâ yok; kayıtlar bekletiliyor.' : `Bir kayıt gönderilemedi: ${err.message}`, err.network ? 'warn' : 'error');
          break;
        }
      }
    } finally {
      setBusy(false);
      renderQueue();
    }
    if (sent === 1 && queue.length === 1 && lastResult) showResult(lastResult);
    else if (sent) toast(`${sent} bekleyen hesaplama geçmişe kaydedildi.`);
  }

  function renderNet() {
    const online = navigator.onLine !== false;
    $('#net-pill').dataset.state = online ? 'online' : 'offline';
    $('#net-label').textContent = online ? 'Çevrimiçi' : 'Çevrimdışı';
  }

  // ── Sonuç raporu ───────────────────────────────────────────────────────
  function shareParts(amortization, personnel, fuel, total) {
    const parts = [['amort', 'Amortisman', amortization], ['pers', 'Personel', personnel], ['fuel', 'Yakıt', fuel]];
    return [
      h('div', { class: 'stack-bar', 'aria-hidden': 'true' },
        parts.map(([key, , value]) => h('span', { class: `seg-${key}`, style: { width: `${share(value, total)}%` } }))),
      h('ul', { class: 'legend' },
        parts.map(([key, label, value]) => h('li', null,
          h('i', { class: `dot seg-${key}` }), label,
          h('b', { class: 'num', text: money(value) }),
          h('em', { class: 'num', text: `%${C.formatNumber(share(value, total), 1)}` })))),
    ];
  }

  function detailGrid(pairs) {
    return h('dl', { class: 'report-grid' },
      pairs.map(([label, value]) => h('div', null, h('dt', { text: label }), h('dd', { class: 'num', text: value }))));
  }

  function gorrapBlock(lines, label) {
    const text = lines.join('\n');
    return h('div', { class: 'gorrap' },
      h('div', { class: 'gorrap-head' },
        h('span', { class: 'gorrap-label', text: label }),
        h('button', {
          type: 'button', class: 'btn small', text: '📋 Kopyala',
          onclick: async () => {
            if (await copyText(text)) toast(lines.length > 1 ? 'GÖRRAP satırları panoya kopyalandı.' : 'GÖRRAP satırı panoya kopyalandı.');
            else toast('Kopyalanamadı; metni seçip kopyalayın.', 'error');
          },
        })),
      lines.map((line) => h('code', { text: line })));
  }

  function report(record, title) {
    return h('article', { class: 'card report' },
      h('header', { class: 'report-head' },
        h('div', null,
          h('span', { class: 'eyebrow', text: title }),
          h('h3', { class: 'num', text: `${record.departure} → ${record.arrival}` }),
          h('span', { class: 'hint', text: `${formatDateTR(record.duty_date)} · ${record.duration_text} · Kayıt #${record.id}` })),
        h('div', { class: 'report-total' },
          h('span', { text: 'Toplam' }),
          h('strong', { class: 'num', text: money(record.total) }),
          h('small', { class: 'num', text: `${money(record.hourly)} / saat` }))),
      ...shareParts(record.amortization, record.personnel_cost, record.fuel_cost, record.total),
      detailGrid([
        ['Gündüz / gece', `☀️ ${record.day_text} · 🌙 ${record.night_text}`],
        ['Yakıt', `${C.formatNumber(record.fuel_liters)} L ${record.fuel_label}`],
        ['Yakıt ağırlığı', `${C.formatMoney(record.fuel_kg)} kg`],
        ['Yakıt verimi', `${C.formatMoney(record.efficiency)} L/saat`],
        [`Litre fiyatı · ${record.fuel_province}`, `${money(record.fuel_price)}/L`],
        ['Euro kuru', money(record.eur_rate, 4)],
        ['Aylık maaş', money(record.monthly_salary)],
        ['Personel', `${record.personnel} kişi`],
      ]),
      gorrapBlock([record.gorrap_line], 'GÖRRAP'));
  }

  function summaryReport(summary, dutyDate) {
    return h('article', { class: 'card report summary-report' },
      h('header', { class: 'report-head' },
        h('div', null,
          h('span', { class: 'eyebrow', text: `Günlük toplam · ${summary.count} görev` }),
          h('h3', { class: 'num', text: formatDateTR(dutyDate) }),
          h('span', { class: 'hint', text: `Görev başı ortalama ${money(summary.average)}` })),
        h('div', { class: 'report-total' },
          h('span', { text: 'Genel toplam' }),
          h('strong', { class: 'num', text: money(summary.total) }))),
      ...shareParts(summary.amortization, summary.personnel_cost, summary.fuel_cost, summary.total),
      detailGrid([
        ['Toplam süre', summary.duration_text],
        ['Gündüz / gece', `☀️ ${summary.day_text} · 🌙 ${summary.night_text}`],
        ['Toplam yakıt', `${C.formatNumber(summary.fuel_liters)} L`],
      ]),
      gorrapBlock(summary.gorrap_lines, 'TÜM GÖRRAP SATIRLARI'));
  }

  function showCalcView() {
    $('#calc-view').hidden = false;
    $('#result-view').hidden = true;
  }

  function showResult(result) {
    const records = result.records;
    $('#result-title').textContent = records.length > 1 ? `${records.length} görev hesaplandı` : 'Hesaplama sonucu';
    $('#result-summary').replaceChildren(...(result.summary ? [summaryReport(result.summary, records[0].duty_date)] : []));
    $('#result-list').replaceChildren(...records.map((record, index) => report(record, records.length > 1 ? `${index + 1}. görev` : 'Görev')));
    $('#calc-view').hidden = true;
    $('#result-view').hidden = false;
    if (location.hash && location.hash !== '#hesapla') location.hash = '#hesapla';
    window.scrollTo({ top: 0 });
    toast('Hesaplandı ve geçmişe kaydedildi.');
  }

  // ── Geçmiş ─────────────────────────────────────────────────────────────
  async function loadHistory(page) {
    try {
      const data = await api('GET', `api/history?page=${page}`);
      historyPage = data.page;
      $('#history-count').textContent = data.total ? `${data.total} kayıt` : '';
      $('#btn-export').hidden = !data.total;
      $('#btn-clear').hidden = !data.total;
      $('#history-list').replaceChildren(...(data.items.length
        ? data.items.map(historyRow)
        : [h('div', { class: 'empty' }, h('b', { text: 'Henüz kayıtlı hesaplama yok.' }), h('p', { text: 'Hesapla sayfasından ilk görevinizi hesaplayın.' }))]));
      $('#history-pager').hidden = data.pages <= 1;
      $('#history-page').textContent = `${data.page + 1} / ${data.pages}`;
      $('#history-prev').disabled = data.page <= 0;
      $('#history-next').disabled = data.page >= data.pages - 1;
    } catch (err) {
      await handleError(err);
    }
  }

  function historyRow(record) {
    return h('button', { type: 'button', class: 'history-item', onclick: () => openRecord(record.id) },
      h('span', { class: 'history-date' },
        h('b', { class: 'num', text: formatDateTR(record.duty_date) }),
        h('small', { text: `#${record.id}` })),
      h('span', { class: 'history-main' },
        h('b', { class: 'num', text: `${record.departure} → ${record.arrival}` }),
        h('small', { text: `${record.duration_text} · ${C.formatNumber(record.fuel_liters)} L ${record.fuel_label} · ${record.personnel} kişi` })),
      h('span', { class: 'history-total num', text: money(record.total) }));
  }

  async function openRecord(id) {
    try {
      recordState = await api('GET', `api/history/${id}`);
      const record = recordState.record;
      $('#record-title').textContent = `Hesap kaydı #${record.id}`;
      const parts = [report(record, `Kaydedildi: ${formatDateTimeTR(record.created_at)}`)];
      if (recordState.batch_size > 1) {
        parts.unshift(h('p', { class: 'note', text: `Bu kayıt ${recordState.batch_size} görevli bir hesaplamanın parçasıdır. O günün genel toplamı: ${money(recordState.batch_summary.total)}.` }));
      }
      $('#record-body').replaceChildren(...parts);
      ui.recordDialog.showModal();
    } catch (err) {
      await handleError(err);
    }
  }

  // ── İstatistik ─────────────────────────────────────────────────────────
  function periodCard(period, change) {
    const hasChange = change !== null && change !== undefined;
    return h('section', { class: 'card' },
      h('div', { class: 'row-between' },
        h('h2', { class: 'card-title', text: period.title }),
        hasChange
          ? h('span', {
            class: change > 0 ? 'badge warning' : 'badge',
            title: 'Geçen ayın tamamına göre',
            text: `${change > 0 ? '▲' : change < 0 ? '▼' : '＝'} %${C.formatNumber(Math.abs(change), 1)}`,
          })
          : null),
      h('div', { class: 'period-total num', text: money(period.total) }),
      h('dl', { class: 'period-rows' },
        [
          ['Görev', String(period.count)],
          ['Toplam süre', period.duration_text],
          ['Yakıt', `${C.formatNumber(period.fuel_liters)} L`],
          ['Görev başı', period.count ? money(period.average) : '—'],
        ].map(([label, value]) => h('div', null, h('dt', { text: label }), h('dd', { class: 'num', text: value })))));
  }

  async function loadStats() {
    try {
      const data = await api('GET', 'api/stats');
      $('#stats-periods').replaceChildren(...data.periods.map((period) => periodCard(period, period.key === 'month' ? data.change_vs_last_month : null)));
      const dist = data.distribution;
      $('#stats-distribution').hidden = !dist;
      if (dist) {
        $('#stats-distribution-title').textContent = `Maliyet dağılımı (${dist.basis})`;
        const [bar, legend] = shareParts(dist.amortization, dist.personnel_cost, dist.fuel_cost, dist.total);
        $('#stats-bar').replaceChildren(...bar.childNodes);
        $('#stats-legend').replaceChildren(...legend.childNodes);
      }
    } catch (err) {
      await handleError(err);
    }
  }

  // ── Yönetim ────────────────────────────────────────────────────────────
  function tile(label, value, alert) {
    return h('div', { class: alert ? 'tile alert' : 'tile' }, h('span', { text: label }), h('b', { class: 'num', text: String(value) }));
  }

  async function loadAdmin() {
    try {
      const data = await api('GET', 'api/admin');
      const overview = data.overview;
      $('#admin-tiles').replaceChildren(
        tile('Bugünkü hesaplama', overview.today),
        tile('Toplam hesaplama', overview.calculations),
        tile('Etkin kişi', overview.active_accounts),
        tile('Onay bekleyen üyelik', overview.pending_accounts, overview.pending_accounts > 0),
        tile('Açık sorun bildirimi', data.issues.length, data.issues.length > 0),
      );
      const max = Math.max(1, ...overview.trend.map((day) => day.count));
      $('#admin-trend').replaceChildren(...overview.trend.map((day) => h('div', { class: 'trend-col' },
        h('b', { class: 'num', text: String(day.count) }),
        h('div', { class: 'trend-bar', style: { height: `${Math.round((day.count / max) * 70)}%` } }),
        h('span', { class: 'num', text: formatDateTR(day.day).slice(0, 5) }))));

      $('#admin-issues').replaceChildren(...(data.issues.length
        ? data.issues.map((issue) => h('li', null,
          h('div', null,
            h('b', { text: issue.display_name }),
            h('small', { text: `@${issue.username} · ${formatDateTimeTR(issue.created_at)}` }),
            h('p', { text: issue.message })),
          h('button', {
            type: 'button', class: 'btn small', text: '✅ Kapat',
            onclick: async () => {
              try {
                await api('POST', `api/admin/issues/${issue.id}/resolve`, {});
                toast('Bildirim kapatıldı.');
                await loadAdmin();
              } catch (err) { await handleError(err); }
            },
          })))
        : [h('li', null, h('span', { class: 'hint', text: 'Açık bildirim yok.' }))]));

      $('#admin-people-table').replaceChildren(
        h('thead', null, h('tr', null, ['Kişi', 'Kullanıcı adı', 'Hesaplama', 'Son hesaplama', 'Son giriş'].map((label) => h('th', { text: label })))),
        h('tbody', null, overview.people.map((person) => h('tr', null,
          h('td', { text: person.display_name }),
          h('td', { text: `@${person.username}` }),
          h('td', { class: 'num', text: String(person.calculations) }),
          h('td', { class: 'num', text: formatDateTimeTR(person.last_calculation) }),
          h('td', { class: 'num', text: formatDateTimeTR(person.last_login) })))));

      $('#admin-activity').replaceChildren(...(data.activity.length
        ? data.activity.map((entry) => h('li', null,
          h('div', null,
            h('b', { text: entry.display_name }),
            h('small', { text: `${ACTIVITY_LABELS[entry.action] || entry.action}${entry.detail ? ` · ${entry.detail}` : ''}` })),
          h('small', { class: 'num', text: formatDateTimeTR(entry.created_at) })))
        : [h('li', null, h('span', { class: 'hint', text: 'Henüz işlem kaydı yok.' }))]));
    } catch (err) {
      await handleError(err);
    }
  }

  // ── Kişiler ────────────────────────────────────────────────────────────
  function personAction(label, handler, className) {
    return h('button', { type: 'button', class: `btn small ${className || ''}`.trim(), text: label, onclick: handler });
  }

  async function updatePerson(id, changes, message) {
    try {
      await api('POST', `api/people/${id}`, changes);
      toast(message);
      await loadPeople();
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  function personRow(person) {
    const badges = h('div', { class: 'badges' },
      person.is_admin ? h('span', { class: 'badge', text: 'Yönetici' }) : null,
      person.approval_status === 'pending' ? h('span', { class: 'badge warning', text: 'Onay bekliyor' }) : null,
      person.approval_status === 'rejected' ? h('span', { class: 'badge muted', text: 'Reddedildi' }) : null,
      person.approval_status === 'approved' && !person.is_active ? h('span', { class: 'badge muted', text: 'Pasif' }) : null,
      person.reset_pending ? h('span', { class: 'badge warning', text: 'Şifre talebi' }) : null,
      person.ha_linked ? h('span', { class: 'badge muted', text: 'HA paneli bağlı' }) : null);

    const info = [];
    if (person.position) info.push(POSITION_NAMES[person.position] || person.position);
    if (person.email) info.push(person.email);
    if (person.phone) info.push(person.phone);
    info.push(person.last_login ? `Son giriş: ${formatDateTimeTR(person.last_login)}` : 'Henüz giriş yapmadı');

    const passwordInput = h('input', { type: 'password', minlength: '8', required: true, placeholder: 'Yeni şifre (en az 8)', autocomplete: 'new-password' });
    const passwordBox = h('form', { class: 'inline-password', hidden: true },
      passwordInput, h('button', { type: 'submit', class: 'btn small primary', text: 'Kaydet' }));
    passwordBox.addEventListener('submit', (event) => {
      event.preventDefault();
      updatePerson(person.id, { password: passwordInput.value }, `${person.display_name} için yeni şifre kaydedildi.`);
    });

    const actions = h('div', { class: 'person-actions' });
    if (person.approval_status !== 'approved') {
      actions.append(personAction('✅ Üyeliği onayla',
        () => updatePerson(person.id, { approval_status: 'approved' }, `${person.display_name} onaylandı.`), 'primary'));
      if (person.approval_status === 'pending') {
        actions.append(personAction('❌ Reddet',
          () => updatePerson(person.id, { approval_status: 'rejected' }, `${person.display_name} reddedildi.`), 'danger'));
      }
    } else {
      actions.append(
        personAction(person.reset_pending ? '🔑 Talebi yanıtla' : '🔑 Şifre ver',
          () => { passwordBox.hidden = !passwordBox.hidden; if (!passwordBox.hidden) passwordInput.focus(); }),
        personAction(person.is_admin ? 'Yöneticiliği kaldır' : 'Yönetici yap',
          () => updatePerson(person.id, { is_admin: !person.is_admin }, 'Yetki güncellendi.')),
        personAction(person.is_active ? 'Pasif yap' : 'Etkinleştir',
          () => updatePerson(person.id, { is_active: !person.is_active }, person.is_active ? 'Kişi pasif yapıldı.' : 'Kişi etkinleştirildi.'),
          person.is_active ? 'danger' : ''),
      );
    }

    return h('li', { class: person.approval_status === 'rejected' ? 'person inactive' : 'person' },
      h('div', { class: 'person-head' },
        h('div', { class: 'person-name' }, h('b', { text: person.display_name }), h('small', { text: `@${person.username}` })),
        badges),
      h('div', { class: 'person-meta', text: info.join(' · ') }),
      actions,
      passwordBox);
  }

  async function loadPeople() {
    const { people } = await api('GET', 'api/people');
    ui.peopleList.replaceChildren(...people.map(personRow));
  }

  async function openPeople() {
    toggleMenu(false);
    try {
      await loadPeople();
      ui.peopleDialog.showModal();
    } catch (error) {
      await handleError(error);
    }
  }

  function toggleMenu(open) {
    ui.accountMenu.hidden = !open;
    ui.accountBtn.setAttribute('aria-expanded', String(open));
  }

  // ── Olaylar: giriş ─────────────────────────────────────────────────────
  ui.loginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    submitForm(ui.loginForm, 'api/login', start);
  });
  ui.registerForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = formData(ui.registerForm);
    if (data.password !== data.again) { formError(ui.registerForm, 'Şifreler aynı değil.'); return; }
    submitForm(ui.registerForm, 'api/register', async () => {
      ui.registerForm.reset();
      showAuthView('login');
      toast('Başvurunuz alındı. Yönetici onayından sonra giriş yapabilirsiniz.');
    });
  });
  ui.resetForm.addEventListener('submit', (event) => {
    event.preventDefault();
    submitForm(ui.resetForm, 'api/password-reset', async () => {
      ui.resetForm.reset();
      showAuthView('login');
      toast('Hesap eşleşirse şifre yenileme talebiniz yöneticiye iletildi.');
    });
  });
  ui.setupForm.addEventListener('submit', (event) => {
    event.preventDefault();
    submitForm(ui.setupForm, 'api/setup', start);
  });
  ui.auth.addEventListener('click', (event) => {
    const button = event.target.closest('[data-auth-view]');
    if (button && session && !session.setup_required) showAuthView(button.dataset.authView);
  });

  // ── Olaylar: hesaplama ─────────────────────────────────────────────────
  ui.duties.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const duty = findDuty(button.closest('.duty').dataset.id);
    if (!duty) return;
    const { action, field } = button.dataset;
    const delta = Number(button.dataset.delta);
    if (action === 'remove') { removeDuty(duty.id); return; }
    if (action === 'nudge') {
      const current = C.parseTime(duty[field]);
      duty[field] = C.formatTime((current === null ? 720 : current) + delta);
    } else if (action === 'now') {
      duty[field] = C.formatTime(minutesOfDay(new Date()));
    } else if (action === 'fuel') {
      duty.fuel_liters = sanitizeFuel(duty.fuel_liters + delta);
    }
    commitDuty(duty);
  });

  ui.duties.addEventListener('input', (event) => {
    const input = event.target.closest('input[data-field]');
    if (!input) return;
    const duty = findDuty(input.closest('.duty').dataset.id);
    if (!duty) return;
    if (input.dataset.field === 'fuel_liters') {
      if (input.value === '') return;
      duty.fuel_liters = sanitizeFuel(input.value);
    } else {
      const value = C.sanitizeTime(input.value, null);
      if (!value) return;
      duty[input.dataset.field] = value;
    }
    commitDuty(duty);
  });

  ui.duties.addEventListener('blur', (event) => {
    const input = event.target.closest && event.target.closest('input[data-field]');
    if (!input) return;
    const duty = findDuty(input.closest('.duty').dataset.id);
    if (duty) setTimeout(() => refreshDuty(duty), 0); // boş/geçersiz girişi son geçerli değere döndür
  }, true);

  $('#btn-add-duty').addEventListener('click', addDuty);
  $('#btn-submit').addEventListener('click', submit);
  $('#btn-copy').addEventListener('click', async () => {
    const text = summaryText();
    if (await copyText(text)) toast('📋 Özet panoya kopyalandı.');
    else toast('Kopyalanamadı.', 'error');
  });
  $('#duty-date').addEventListener('change', (event) => {
    form.dutyDate = event.target.value || todayISO();
  });
  for (const radio of $$('input[name="fuel_type"]')) {
    radio.addEventListener('change', () => {
      form.fuelType = radio.value === 'gasoline' ? 'gasoline' : 'diesel';
      renderMarket();
      form.duties.forEach(refreshDuty);
      refreshSummary();
      saveDraft();
    });
  }
  for (const button of $$('[data-personnel-delta]')) {
    button.addEventListener('click', () => setPersonnel(form.personnel + Number(button.dataset.personnelDelta)));
  }
  for (const pill of $$('#personnel-presets .pill')) {
    pill.addEventListener('click', () => setPersonnel(pill.dataset.personnel));
  }
  $('#personnel').addEventListener('input', (event) => {
    if (event.target.value !== '') setPersonnel(event.target.value);
  });
  $('#personnel').addEventListener('blur', (event) => {
    event.target.value = String(form.personnel);
  });
  for (const chip of $$('[data-preset]')) {
    chip.addEventListener('click', () => applyPreset(chip.dataset.preset));
  }
  $('[data-queue="send"]').addEventListener('click', sendQueue);
  $('[data-queue="clear"]').addEventListener('click', () => {
    if (!window.confirm('Bekleyen bütün hesaplamalar silinsin mi?')) return;
    storageSet(queueKey(), []);
    renderQueue();
  });
  $('#result-edit').addEventListener('click', () => { showCalcView(); window.scrollTo({ top: 0 }); });
  $('#result-new').addEventListener('click', () => {
    applySnapshot({ personnel: form.personnel, fuel_type: form.fuelType, duties: [DEFAULT_DUTY] });
    form.dutyDate = todayISO();
    syncStaticInputs();
    renderDuties();
    saveDraft();
    showCalcView();
    window.scrollTo({ top: 0 });
  });
  window.addEventListener('online', () => {
    if (!boot) return;
    renderNet();
    renderQueue();
    if (getQueue().length) toast(`Bağlantı geri geldi. ${getQueue().length} bekleyen hesaplama gönderilebilir.`);
  });
  window.addEventListener('offline', () => {
    if (!boot) return;
    renderNet();
    renderQueue();
    toast('Çevrimdışısınız. Kaydettiğiniz hesaplamalar bu cihazda bekletilecek.', 'warn');
  });

  // ── Olaylar: geçmiş, ayarlar, yönetim ──────────────────────────────────
  $('#history-prev').addEventListener('click', () => loadHistory(historyPage - 1));
  $('#history-next').addEventListener('click', () => loadHistory(historyPage + 1));
  $('#btn-clear').addEventListener('click', async () => {
    if (!window.confirm('Size ait bütün hesaplama kayıtları kalıcı olarak silinecek. Emin misiniz?')) return;
    try {
      const data = await api('POST', 'api/history/clear', {});
      boot.last_inputs = null;
      historyPage = 0;
      toast(`${data.removed} kayıt silindi.`);
      await loadHistory(0);
    } catch (err) {
      await handleError(err);
    }
  });
  $('#record-delete').addEventListener('click', async () => {
    if (!recordState || !window.confirm(`Kayıt #${recordState.record.id} silinsin mi? Bu işlem geri alınamaz.`)) return;
    try {
      await api('POST', `api/history/${recordState.record.id}/delete`, {});
      ui.recordDialog.close();
      toast(`Kayıt #${recordState.record.id} silindi.`);
      await loadHistory(historyPage);
    } catch (err) {
      await handleError(err);
    }
  });
  $('#record-reuse').addEventListener('click', () => {
    if (!recordState) return;
    applySnapshot(recordState.inputs);
    form.dutyDate = todayISO();
    syncStaticInputs();
    renderMarket();
    renderDuties();
    saveDraft();
    ui.recordDialog.close();
    showCalcView();
    location.hash = '#hesapla';
    toast('Kayıttaki değerler hesaplama formuna yüklendi.');
  });

  ui.settingsForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = $('button[type=submit]', ui.settingsForm);
    formError(ui.settingsForm, '');
    button.disabled = true;
    const previousProvince = boot.settings.fuel_province;
    try {
      const data = await api('POST', 'api/settings', formData(ui.settingsForm));
      boot.settings = data.settings;
      boot.market = data.market;
      fillSettings();
      renderMarket();
      renderDuties();
      toast('Sabit ayarlar kaydedildi.');
      if (data.settings.fuel_province !== previousProvince && data.market.diesel === null) pollMarket(6);
    } catch (err) {
      if (err.status === 401) await start();
      else formError(ui.settingsForm, err.message);
    } finally {
      button.disabled = false;
    }
  });
  $('#btn-refresh').addEventListener('click', async () => {
    if (busy) return;
    setBusy(true, 'Euro ve akaryakıt fiyatları kontrol ediliyor…');
    try {
      const data = await api('POST', 'api/market/refresh', {});
      boot.market = data.market;
      renderMarket();
      renderDuties();
      const ok = data.eur_ok && data.fuel_ok;
      toast(ok ? 'Otomatik veriler güncellendi.' : 'Bazı veriler alınamadı; son başarılı değerler korunuyor.', ok ? '' : 'warn');
    } catch (err) {
      await handleError(err);
    } finally {
      setBusy(false);
    }
  });
  $('#admin-refresh').addEventListener('click', loadAdmin);
  $('#admin-people').addEventListener('click', openPeople);

  // ── Olaylar: hesap menüsü ve pencereler ────────────────────────────────
  ui.accountBtn.addEventListener('click', (event) => { event.stopPropagation(); toggleMenu(ui.accountMenu.hidden); });
  document.addEventListener('click', (event) => { if (!ui.accountMenu.contains(event.target)) toggleMenu(false); });
  ui.accountMenu.addEventListener('click', (event) => {
    const command = event.target.closest('[data-cmd]');
    if (!command) return;
    toggleMenu(false);
    if (command.dataset.cmd === 'logout') logout();
    if (command.dataset.cmd === 'people') openPeople();
    if (command.dataset.cmd === 'issue') {
      ui.issueForm.reset();
      formError(ui.issueForm, '');
      ui.issueDialog.showModal();
      setTimeout(() => $('textarea', ui.issueForm).focus(), 30);
    }
    if (command.dataset.cmd === 'password') {
      ui.passwordForm.reset();
      formError(ui.passwordForm, '');
      ui.passwordDialog.showModal();
    }
  });
  for (const close of $$('[data-close]')) {
    close.addEventListener('click', () => close.closest('dialog').close());
  }
  ui.passwordForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = formData(ui.passwordForm);
    if (data.new !== data.again) { formError(ui.passwordForm, 'Yeni şifreler aynı değil.'); return; }
    submitForm(ui.passwordForm, 'api/password', async () => {
      ui.passwordDialog.close();
      toast('Şifreniz değiştirildi.');
    });
  });
  ui.issueForm.addEventListener('submit', (event) => {
    event.preventDefault();
    submitForm(ui.issueForm, 'api/issues', async () => {
      ui.issueDialog.close();
      ui.issueForm.reset();
      toast('Sorun bildiriminiz yöneticiye iletildi.');
    });
  });
  ui.personForm.addEventListener('submit', (event) => {
    event.preventDefault();
    submitForm(ui.personForm, 'api/people', async () => {
      const name = ui.personForm.elements.display_name.value;
      ui.personForm.reset();
      toast(`${name} eklendi. Kullanıcı adını ve şifresini kendisine iletin.`);
      await loadPeople();
    });
  });

  window.addEventListener('hashchange', route);

  start();
})();
