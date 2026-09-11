// Telegram Mini App — Görev Maliyet Hesaplayıcı (v3.7)

(function () {
  'use strict';

  const tg = window.Telegram && window.Telegram.WebApp;
  const IN_TELEGRAM = Boolean(tg && tg.platform && tg.platform !== 'unknown');
  const C = window.GorevCalc;

  const MAX_DUTIES = 12;
  const DEFAULT_DUTY = { departure: '09:35', arrival: '19:25', fuel_liters: 750 };
  const FUEL_LABELS = { diesel: 'Dizel', gasoline: 'Benzin' };
  const PRICE_LABELS = { diesel: 'motorin', gasoline: 'benzin' };
  const NUDGES = [-60, -15, -5, 5, 15, 60];

  const $ = (selector, root) => (root || document).querySelector(selector);
  const $$ = (selector, root) => Array.from((root || document).querySelectorAll(selector));
  const reducedMotion = () => Boolean(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  // ---------- Telegram yardımcıları ----------
  function haptic(type) {
    try {
      const feedback = IN_TELEGRAM && tg.HapticFeedback;
      if (!feedback) return;
      if (type === 'success' || type === 'error' || type === 'warning') feedback.notificationOccurred(type);
      else if (type === 'selection') feedback.selectionChanged();
      else feedback.impactOccurred(type || 'light');
    } catch (err) {
      // Eski istemcilerde titreşim desteklenmeyebilir.
    }
  }

  function showAlert(message) {
    if (IN_TELEGRAM && tg.showAlert) {
      try {
        tg.showAlert(message);
        return;
      } catch (err) {
        // Tarayıcı uyarısına düş.
      }
    }
    window.alert(message);
  }

  function confirmAction(message, onConfirm) {
    if (IN_TELEGRAM && tg.showConfirm) {
      try {
        tg.showConfirm(message, (ok) => ok && onConfirm());
        return;
      } catch (err) {
        // Tarayıcı onayına düş.
      }
    }
    if (window.confirm(message)) onConfirm();
  }

  let toastTimer = null;
  function toast(message, tone) {
    const el = $('#toast');
    el.textContent = message;
    el.dataset.tone = tone || 'info';
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
  }

  // ---------- Tarih ve biçim ----------
  const pad = (value) => String(value).padStart(2, '0');
  const todayISO = (date) => {
    const d = date || new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  };
  const minutesOfDay = (date) => date.getHours() * 60 + date.getMinutes();
  const formatDateTR = (iso) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    return match ? `${match[3]}.${match[2]}.${match[1]}` : '—';
  };
  const clockDuration = (minutes) => `${Math.floor(minutes / 60)}:${pad(minutes % 60)}`;
  const money = (value, decimals) => `₺${C.formatMoney(value, decimals)}`;

  // ---------- Bot tarafından adrese eklenen önizleme verileri ----------
  const market = (function readMarketParams() {
    const query = new URLSearchParams(window.location.search);
    const number = (key) => {
      const raw = query.get(key);
      if (raw === null || raw === '') return null;
      const value = Number(raw);
      return Number.isFinite(value) && value >= 0 ? value : null;
    };
    const dataDate = query.get('tarih') || '';
    return {
      eur: number('eur'),
      diesel: number('dz'),
      gasoline: number('bz'),
      salary: number('maas'),
      amort: number('amort') === null ? 70 : number('amort'),
      fuelProvince: (query.get('il') || '').slice(0, 40),
      solarProvince: (query.get('gil') || '').slice(0, 40),
      sunrise: C.sanitizeTime(query.get('gd'), null),
      sunset: C.sanitizeTime(query.get('gb'), null),
      dataDate: /^\d{4}-\d{2}-\d{2}$/.test(dataDate) ? dataDate : null,
    };
  })();

  // ---------- Durum ----------
  const state = {
    dutyDate: todayISO(),
    fuelType: 'diesel',
    personnel: 4,
    duties: [],
    nextId: 1,
  };

  const fuelPrice = () => (state.fuelType === 'gasoline' ? market.gasoline : market.diesel);
  const hasPricing = () => market.eur !== null && market.salary !== null && fuelPrice() !== null;
  const hasSun = () => market.sunrise !== null && market.sunset !== null;

  function sanitizeFuel(value) {
    const n = Number(String(value).replace(',', '.'));
    return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) / 100 : 0;
  }

  function sanitizePersonnel(value) {
    const n = parseInt(value, 10);
    return Number.isFinite(n) ? Math.min(50, Math.max(1, n)) : 4;
  }

  function makeDuty(values) {
    const source = values || {};
    return {
      id: state.nextId++,
      departure: C.sanitizeTime(source.departure, DEFAULT_DUTY.departure),
      arrival: C.sanitizeTime(source.arrival, DEFAULT_DUTY.arrival),
      fuel_liters: source.fuel_liters == null ? DEFAULT_DUTY.fuel_liters : sanitizeFuel(source.fuel_liters),
    };
  }

  function applySnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return false;
    state.personnel = sanitizePersonnel(snapshot.personnel);
    state.fuelType = snapshot.fuel_type === 'gasoline' ? 'gasoline' : 'diesel';
    const list = Array.isArray(snapshot.duties) ? snapshot.duties.slice(0, MAX_DUTIES) : [];
    state.nextId = 1;
    state.duties = list.length ? list.map(makeDuty) : [makeDuty(DEFAULT_DUTY)];
    return true;
  }

  function snapshot() {
    return {
      personnel: state.personnel,
      fuel_type: state.fuelType,
      duties: state.duties.map(({ departure, arrival, fuel_liters }) => ({ departure, arrival, fuel_liters })),
    };
  }

  const saveDraft = () => Store.saveDraft(snapshot());
  const findDuty = (id) => state.duties.find((duty) => String(duty.id) === String(id));

  // ---------- Hesap ----------
  function dutyMetrics(duty) {
    const minutes = C.durationMinutes(duty.departure, duty.arrival);
    return {
      minutes,
      kg: duty.fuel_liters * C.DENSITY[state.fuelType],
      light: hasSun() ? C.splitDaylight(duty.departure, duty.arrival, market.sunrise, market.sunset) : null,
      cost: hasPricing()
        ? C.calculate({
            minutes,
            eur: market.eur,
            salary: market.salary,
            personnel: state.personnel,
            liters: duty.fuel_liters,
            price: fuelPrice(),
            fuelType: state.fuelType,
            dailyAmortEur: market.amort,
          })
        : null,
    };
  }

  function totals() {
    const sum = { minutes: 0, liters: 0, day: 0, night: 0, amortization: 0, personnelCost: 0, fuelCost: 0, total: 0 };
    state.duties.forEach((duty) => {
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
    });
    return sum;
  }

  // ---------- Görev kartları ----------
  function nudgeLabel(delta) {
    const sign = delta < 0 ? '−' : '+';
    return Math.abs(delta) === 60 ? `${sign}1 sa` : `${sign}${Math.abs(delta)}`;
  }

  function timeBox(field, icon, label) {
    return `
      <div class="time-box">
        <div class="time-box-head">
          <span>${icon} ${label}</span>
          <button type="button" class="link-btn" data-action="now" data-field="${field}">Şimdi</button>
        </div>
        <input type="time" class="time-input num" data-field="${field}" aria-label="${label} saati">
        <div class="nudge">
          ${NUDGES.map((d) => `<button type="button" data-action="nudge" data-field="${field}" data-delta="${d}">${nudgeLabel(d)}</button>`).join('')}
        </div>
      </div>`;
  }

  function dutyTemplate(duty, index) {
    const removable = state.duties.length > 1;
    const sunStyle = hasSun()
      ? ` style="--sr:${((C.parseTime(market.sunrise) / C.DAY_MINUTES) * 100).toFixed(2)}%;--ss:${((C.parseTime(market.sunset) / C.DAY_MINUTES) * 100).toFixed(2)}%"`
      : '';
    return `
      <article class="card duty" data-id="${duty.id}">
        <header class="duty-head">
          <div class="duty-title"><span class="duty-num num">${index + 1}</span>Görev</div>
          <div class="duty-actions">
            <span class="badge num" data-role="duration"></span>
            ${removable ? `<button type="button" class="icon-btn" data-action="remove" aria-label="${index + 1}. görevi sil">✕</button>` : ''}
          </div>
        </header>
        <div class="grid-2">
          ${timeBox('departure', '🚀', 'Avara')}
          ${timeBox('arrival', '⚓', 'Aborda')}
        </div>
        <div class="timeline" aria-hidden="true">
          <div class="tl-track${hasSun() ? '' : ' no-sun'}"${sunStyle}><div data-role="segments"></div></div>
          <div class="tl-scale">
            <span style="left:0">00</span><span style="left:25%">06</span><span style="left:50%">12</span><span style="left:75%">18</span><span style="left:100%">24</span>
          </div>
        </div>
        <div class="fuel-row">
          <div>
            <span class="field-label">Harcanan yakıt</span>
            <small class="hint num" data-role="kg"></small>
          </div>
          <div class="stepper wide">
            <button type="button" data-action="fuel" data-delta="-5" aria-label="5 litre azalt">−</button>
            <input type="number" class="num" data-field="fuel_liters" inputmode="decimal" min="0" step="any" aria-label="Yakıt litresi">
            <span class="unit">L</span>
            <button type="button" data-action="fuel" data-delta="5" aria-label="5 litre artır">+</button>
          </div>
        </div>
        <div class="pill-row">
          ${[-50, -15, 15, 50].map((d) => `<button type="button" class="pill" data-action="fuel" data-delta="${d}">${d < 0 ? '−' : '+'}${Math.abs(d)} L</button>`).join('')}
        </div>
        <footer class="duty-foot" data-role="foot">
          <span class="hint num" data-role="light"></span>
          <strong class="num" data-role="cost"></strong>
        </footer>
      </article>`;
  }

  function renderDuties(options) {
    const container = $('#duties');
    container.innerHTML = state.duties.map(dutyTemplate).join('');
    if (options && options.animateId) {
      const card = $(`.duty[data-id="${options.animateId}"]`);
      if (card) card.classList.add('enter');
    }
    state.duties.forEach(refreshDuty);
    refreshSummary();
  }

  function refreshDuty(duty) {
    const card = $(`.duty[data-id="${duty.id}"]`);
    if (!card) return;
    const metrics = dutyMetrics(duty);

    $$('[data-field]', card).forEach((input) => {
      if (document.activeElement === input) return; // yazarken imleci bozma
      input.value = input.dataset.field === 'fuel_liters' ? String(duty.fuel_liters) : duty[input.dataset.field];
    });

    card.classList.toggle('is-invalid', metrics.minutes === 0);
    $('[data-role="duration"]', card).textContent = metrics.minutes === 0 ? 'Süre 0' : C.formatDuration(metrics.minutes);
    $('[data-role="kg"]', card).textContent = `≈ ${C.formatNumber(metrics.kg, 0)} kg ${FUEL_LABELS[state.fuelType].toLowerCase()}`;

    const start = C.parseTime(duty.departure);
    const segments = [];
    if (start !== null && metrics.minutes > 0) {
      const end = start + metrics.minutes;
      segments.push([start, Math.min(end, C.DAY_MINUTES)]);
      if (end > C.DAY_MINUTES) segments.push([0, end - C.DAY_MINUTES]);
    }
    const pct = (value) => `${((value / C.DAY_MINUTES) * 100).toFixed(3)}%`;
    $('[data-role="segments"]', card).innerHTML = segments
      .map(([from, to]) => `<span class="tl-seg" style="left:${pct(from)};width:${pct(to - from)}"></span>`)
      .join('');

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
    if (state.duties.length >= MAX_DUTIES) {
      toast(`En fazla ${MAX_DUTIES} görev eklenebilir.`, 'warn');
      return;
    }
    const last = state.duties[state.duties.length - 1];
    const departure = last ? last.arrival : '12:00';
    const duty = makeDuty({
      departure,
      arrival: C.formatTime(C.parseTime(departure) + 120),
      fuel_liters: 250,
    });
    state.duties.push(duty);
    haptic('medium');
    renderDuties({ animateId: duty.id });
    saveDraft();
    const card = $(`.duty[data-id="${duty.id}"]`);
    if (card && card.scrollIntoView) card.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  function removeDuty(id) {
    if (state.duties.length <= 1) return;
    haptic('warning');
    state.duties = state.duties.filter((duty) => String(duty.id) !== String(id));
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
    if (card.scrollIntoView) card.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  // ---------- Özet, üst bilgi, butonlar ----------
  let lastTotalText = '';

  function refreshSummary() {
    const sum = totals();
    const priced = hasPricing();
    const count = state.duties.length;

    $('#sum-label').textContent = priced ? 'Tahmini toplam maliyet' : 'Toplam görev süresi';
    $('#sum-count').textContent = `${count} görev`;
    const totalText = priced ? money(sum.total) : C.formatDuration(sum.minutes);
    const totalEl = $('#sum-total');
    if (totalText !== lastTotalText) {
      totalEl.textContent = totalText;
      if (lastTotalText && !reducedMotion()) {
        totalEl.classList.remove('bump');
        void totalEl.offsetWidth;
        totalEl.classList.add('bump');
      }
      lastTotalText = totalText;
    }

    $('#sum-priced').hidden = !priced;
    if (priced) {
      [
        ['amort', sum.amortization],
        ['pers', sum.personnelCost],
        ['fuel', sum.fuelCost],
      ].forEach(([key, value]) => {
        const share = C.percent(value, sum.total);
        $(`#bar-${key}`).style.width = `${share}%`;
        $(`#lg-${key}`).textContent = money(value);
        $(`#pc-${key}`).textContent = `%${C.formatNumber(share, 1)}`;
      });
    }

    const hours = sum.minutes / 60;
    $('#st-duration').textContent = C.formatDuration(sum.minutes);
    $('#st-fuel').textContent = `${C.formatNumber(sum.liters)} L`;
    if (priced) {
      $('#st-3-label').textContent = 'Saatlik ortalama';
      $('#st-3').textContent = hours > 0 ? money(sum.total / hours, 0) : '—';
    } else {
      $('#st-3-label').textContent = 'Personel';
      $('#st-3').textContent = `${state.personnel} kişi`;
    }
    if (hasSun()) {
      $('#st-4-label').textContent = 'Gündüz / gece';
      $('#st-4').textContent = `☀️ ${clockDuration(sum.day)} · 🌙 ${clockDuration(sum.night)}`;
    } else {
      $('#st-4-label').textContent = 'Yakıt verimi';
      $('#st-4').textContent = hours > 0 ? `${C.formatNumber(sum.liters / hours, 1)} L/sa` : '—';
    }

    if (priced) {
      const province = market.fuelProvince ? `${market.fuelProvince} ` : '';
      const dated = market.dataDate ? ` · ${formatDateTR(market.dataDate)} verisi` : '';
      $('#sum-note').textContent = `${province}${PRICE_LABELS[state.fuelType]} ${money(fuelPrice())}/L · Euro ${money(market.eur)} · ${state.personnel} kişi${dated}`;
    } else {
      $('#sum-note').textContent = 'Maliyet önizlemesi için Mini App\'i sohbetteki 📱 Mini App Aç klavye butonundan açın.';
    }

    $$('#personnel-presets .pill').forEach((pill) => {
      pill.classList.toggle('active', Number(pill.dataset.personnel) === state.personnel);
    });

    updateMainButton(sum);
  }

  function updateMainButton(sum) {
    let label;
    if (!Sync.isOnline()) label = '💾 ÇEVRİMDIŞI KAYDET';
    else if (hasPricing()) label = `✅ HESAPLA · ${money(sum.total, 0)}`;
    else label = state.duties.length > 1 ? `✅ ${state.duties.length} GÖREVİ HESAPLA` : '✅ HESAPLA VE GÖNDER';
    if (IN_TELEGRAM && tg.MainButton) tg.MainButton.setText(label);
    $('#btn-submit-label').textContent = label;
  }

  function showNotice(text) {
    $('#notice-text').textContent = text || '';
    $('#notice').hidden = !text;
  }

  function renderMarket() {
    const strip = $('#market-strip');
    const anyData = market.eur !== null || market.salary !== null || fuelPrice() !== null;
    strip.hidden = !anyData;
    $('#mk-eur').textContent = market.eur !== null ? money(market.eur) : '—';
    $('#mk-fuel-label').textContent = PRICE_LABELS[state.fuelType];
    $('#mk-fuel-label').parentElement.title = market.fuelProvince ? `${market.fuelProvince} ${PRICE_LABELS[state.fuelType]}` : '';
    $('#mk-fuel').textContent = fuelPrice() !== null ? money(fuelPrice()) : '—';
    $('#mk-salary').textContent = market.salary !== null ? money(market.salary, 0) : '—';

    if (hasSun()) {
      const place = market.solarProvince ? `${market.solarProvince} · ` : '';
      $('#hero-sub').textContent = `${place}🌅 ${market.sunrise} · 🌇 ${market.sunset}`;
    }

    if (!anyData && IN_TELEGRAM) {
      showNotice('Maliyet önizlemesi kapalı. Sohbete /start yazıp klavyedeki 📱 Mini App Aç butonuyla yeniden açın.');
    } else if (market.dataDate) {
      const days = Math.round((Date.parse(todayISO()) - Date.parse(market.dataDate)) / 86400000);
      showNotice(days >= 2 ? `Önizleme fiyatları ${days} gün önceye ait. Güncellemek için sohbete /start yazın.` : '');
    }
  }

  function renderNet() {
    const online = Sync.isOnline();
    const pill = $('#net-pill');
    pill.dataset.state = online ? 'online' : 'offline';
    $('#net-label').textContent = online ? 'Çevrimiçi' : 'Çevrimdışı';
  }

  function renderQueue() {
    const queue = Store.getQueue();
    $('#queue-card').hidden = queue.length === 0;
    if (!queue.length) return;
    const online = Sync.isOnline();
    $('#queue-count').textContent = String(queue.length);
    $('#queue-hint').textContent = online
      ? 'Bağlantı var — kayıtları bota gönderebilirsiniz.'
      : 'Bağlantı bekleniyor. Kayıtlar bu cihazda güvende.';
    $('[data-queue="send"]').disabled = !online;

    const list = $('#queue-list');
    list.replaceChildren(
      ...queue.map((item) => {
        const data = item.data || {};
        const dutyCount = Array.isArray(data.duties) ? data.duties.length : 1;
        const li = document.createElement('li');
        const info = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = `${formatDateTR(data.duty_date)} · ${dutyCount} görev · ${data.personnel || '—'} kişi`;
        const saved = document.createElement('small');
        const when = new Date(item.timestamp || item.id);
        saved.textContent = Number.isNaN(when.getTime())
          ? 'Kaydedildi'
          : `Kaydedildi ${pad(when.getDate())}.${pad(when.getMonth() + 1)} ${pad(when.getHours())}:${pad(when.getMinutes())}`;
        info.append(title, saved);
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'icon-btn';
        remove.textContent = '✕';
        remove.setAttribute('aria-label', 'Kaydı sil');
        remove.addEventListener('click', () => {
          Store.removeFromQueue([item.id]);
          haptic('warning');
          renderQueue();
        });
        li.append(info, remove);
        return li;
      })
    );
  }

  // ---------- Gönderim ----------
  function validate() {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(state.dutyDate)) return { message: 'Görev tarihini seçin.' };
    for (let i = 0; i < state.duties.length; i += 1) {
      const duty = state.duties[i];
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
    return {
      v: 2,
      duties: state.duties.map((duty) => ({
        departure: duty.departure,
        arrival: duty.arrival,
        fuel_liters: duty.fuel_liters,
      })),
      personnel: state.personnel,
      fuel_type: state.fuelType,
      duty_date: state.dutyDate,
    };
  }

  function sendFailed(backupQueue) {
    Store.replaceQueue(backupQueue);
    renderQueue();
    haptic('error');
    showAlert('Veri bota gönderilemedi.\n\nMini App\'i sohbetin altındaki 📱 Mini App Aç klavye butonundan açtığınızdan emin olun.');
  }

  function saveOffline(payload) {
    if (Store.enqueue(payload)) {
      haptic('success');
      toast('💾 Çevrimdışı kaydedildi. Bağlantı gelince bekleyenlerden gönderin.', 'ok');
      renderQueue();
    } else {
      haptic('error');
      showAlert('Kayıt yapılamadı: cihaz depolaması kullanılamıyor.');
    }
  }

  function submit() {
    const error = validate();
    if (error) {
      haptic('error');
      if (error.id) flagDuty(error.id);
      showAlert(error.message);
      return;
    }

    const payload = buildPayload();
    Store.saveLastSubmitted(payload);
    saveDraft();

    if (!Sync.isOnline()) {
      saveOffline(payload);
      return;
    }

    if (!IN_TELEGRAM) {
      haptic('success');
      showAlert(`Tarayıcı önizleme modu.\n\nTelegram içinde bu veri bota gönderilir:\n\n${JSON.stringify(payload, null, 2)}`);
      return;
    }

    // Bekleyen çevrimdışı kayıtlar varsa ve sığıyorsa aynı gönderime eklenir.
    const backup = Store.getQueue();
    let outgoing = payload;
    if (backup.length) {
      const candidates = backup.concat({ id: 'current', data: payload });
      if (Sync.takeSendable(candidates).length === candidates.length) {
        outgoing = Sync.buildBatchPayload(candidates);
        Store.clearQueue();
      }
    }
    haptic('success');
    Sync.sendToBot(outgoing, () => sendFailed(backup));
  }

  function sendQueue() {
    if (!Sync.isOnline()) {
      toast('Bağlantı yok. Kayıtlar bekletiliyor.', 'warn');
      return;
    }
    if (!IN_TELEGRAM) {
      showAlert('Bekleyen kayıtlar yalnızca Telegram içinde bota gönderilebilir.');
      return;
    }
    const backup = Store.getQueue();
    const items = Sync.takeSendable(backup);
    if (!items.length) {
      showAlert('Kayıt tek gönderim sınırını aşıyor.');
      return;
    }
    Store.removeFromQueue(items.map((item) => item.id));
    haptic('success');
    Sync.sendToBot(Sync.buildBatchPayload(items), () => sendFailed(backup));
  }

  function summaryText() {
    const sum = totals();
    const lines = [
      '📋 Görev Özeti',
      `📅 ${formatDateTR(state.dutyDate)} · 👥 ${state.personnel} kişi · 🛢 ${FUEL_LABELS[state.fuelType]}`,
      '',
    ];
    state.duties.forEach((duty, index) => {
      const metrics = dutyMetrics(duty);
      const cost = metrics.cost ? ` · ≈ ${money(metrics.cost.total)}` : '';
      lines.push(
        `${index + 1}. Görev: ${duty.departure}–${duty.arrival} (${C.formatDuration(metrics.minutes)}) · ${C.formatNumber(duty.fuel_liters)} L${cost}`
      );
    });
    lines.push('', `⏱ Toplam süre: ${C.formatDuration(sum.minutes)} · ⛽ ${C.formatNumber(sum.liters)} L`);
    if (hasPricing()) lines.push(`💰 Tahmini toplam: ${money(sum.total)}`);
    return lines.join('\n');
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try {
        ok = document.execCommand('copy');
      } catch (copyErr) {
        ok = false;
      }
      area.remove();
      return ok;
    }
  }

  // ---------- Olaylar ----------
  function applyPreset(kind) {
    if (kind === 'last') {
      const last = Store.loadLastSubmitted();
      if (!last) {
        toast('Henüz gönderilmiş bir görev yok.', 'warn');
        return;
      }
      applySnapshot(last);
      if (last.duty_date) state.dutyDate = last.duty_date;
      toast('Son gönderilen görev yüklendi.', 'ok');
    } else if (kind === 'recent') {
      const now = new Date();
      const fuel = state.duties[0] ? state.duties[0].fuel_liters : 500;
      state.nextId = 1;
      state.duties = [
        makeDuty({
          departure: C.formatTime(minutesOfDay(now) - 240),
          arrival: C.formatTime(minutesOfDay(now)),
          fuel_liters: fuel,
        }),
      ];
      state.dutyDate = todayISO(now);
    } else if (kind === 'sample') {
      applySnapshot({ personnel: 4, fuel_type: 'diesel', duties: [DEFAULT_DUTY] });
    }
    haptic('medium');
    syncStaticInputs();
    renderMarket();
    renderDuties();
    saveDraft();
  }

  function syncStaticInputs() {
    $('#duty-date').value = state.dutyDate;
    $('#personnel').value = String(state.personnel);
    const radio = $(`input[name="fuel_type"][value="${state.fuelType}"]`);
    if (radio) radio.checked = true;
  }

  function setPersonnel(value) {
    state.personnel = sanitizePersonnel(value);
    if (document.activeElement !== $('#personnel')) $('#personnel').value = String(state.personnel);
    state.duties.forEach(refreshDuty);
    refreshSummary();
    saveDraft();
  }

  function bindEvents() {
    const duties = $('#duties');

    duties.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-action]');
      if (!button) return;
      const card = button.closest('.duty');
      const duty = card && findDuty(card.dataset.id);
      if (!duty) return;
      const { action, field } = button.dataset;
      const delta = Number(button.dataset.delta);

      if (action === 'remove') {
        removeDuty(duty.id);
        return;
      }
      if (action === 'nudge') {
        const current = C.parseTime(duty[field]);
        duty[field] = C.formatTime((current === null ? 720 : current) + delta);
        haptic('selection');
      } else if (action === 'now') {
        duty[field] = C.formatTime(minutesOfDay(new Date()));
        haptic('medium');
      } else if (action === 'fuel') {
        duty.fuel_liters = sanitizeFuel(duty.fuel_liters + delta);
        haptic('selection');
      }
      commitDuty(duty);
    });

    duties.addEventListener('input', (event) => {
      const input = event.target.closest('[data-field]');
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

    duties.addEventListener(
      'blur',
      (event) => {
        const input = event.target.closest('[data-field]');
        if (!input) return;
        const duty = findDuty(input.closest('.duty').dataset.id);
        if (duty) refreshDuty(duty); // boş/geçersiz girişi son geçerli değere döndür
      },
      true
    );

    $('#btn-add-duty').addEventListener('click', addDuty);
    $('#btn-submit').addEventListener('click', submit);

    $('#duty-date').addEventListener('change', (event) => {
      state.dutyDate = event.target.value || todayISO();
    });

    $$('input[name="fuel_type"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        state.fuelType = radio.value === 'gasoline' ? 'gasoline' : 'diesel';
        haptic('selection');
        renderMarket();
        state.duties.forEach(refreshDuty);
        refreshSummary();
        saveDraft();
      });
    });

    $$('[data-personnel-delta]').forEach((button) => {
      button.addEventListener('click', () => {
        haptic('selection');
        setPersonnel(state.personnel + Number(button.dataset.personnelDelta));
      });
    });
    $$('#personnel-presets .pill').forEach((pill) => {
      pill.addEventListener('click', () => {
        haptic('medium');
        setPersonnel(pill.dataset.personnel);
      });
    });
    const personnelInput = $('#personnel');
    personnelInput.addEventListener('input', () => {
      if (personnelInput.value !== '') setPersonnel(personnelInput.value);
    });
    personnelInput.addEventListener('blur', () => {
      personnelInput.value = String(state.personnel);
    });

    $$('[data-preset]').forEach((chip) => {
      chip.addEventListener('click', () => applyPreset(chip.dataset.preset));
    });

    $('[data-queue="send"]').addEventListener('click', sendQueue);
    $('[data-queue="clear"]').addEventListener('click', () => {
      confirmAction('Bekleyen tüm kayıtlar silinsin mi?', () => {
        Store.clearQueue();
        haptic('warning');
        renderQueue();
      });
    });

    $('#btn-copy').addEventListener('click', async () => {
      if (await copyText(summaryText())) {
        haptic('success');
        toast('📋 Özet panoya kopyalandı.', 'ok');
      } else {
        haptic('warning');
        showAlert(summaryText());
      }
    });

    Sync.onChange((online) => {
      renderNet();
      renderQueue();
      refreshSummary();
      const pending = Store.getQueue().length;
      if (online && pending) toast(`Bağlantı geri geldi. ${pending} bekleyen kayıt gönderilebilir.`, 'ok');
      else if (!online) toast('Çevrimdışısınız. Hesaplamalar cihazda saklanacak.', 'warn');
    });
  }

  // ---------- Başlatma ----------
  function applyTheme() {
    if (IN_TELEGRAM) document.documentElement.dataset.theme = tg.colorScheme === 'dark' ? 'dark' : 'light';
  }

  function renderWrongLaunch() {
    $('#app').innerHTML = `
      <section class="card shield">
        <div class="shield-icon" aria-hidden="true">📱</div>
        <h2>Klavye butonundan açın</h2>
        <p>Telegram, Mini App'in bota veri gönderebilmesi için uygulamanın sohbetin altındaki <b>klavye butonundan</b> açılmasını zorunlu tutar.</p>
        <ol>
          <li>Bu pencereyi kapatın.</li>
          <li>Sohbete <b>/start</b> yazın.</li>
          <li>Klavye alanındaki <b>📱 Mini App Aç</b> butonuna dokunun.</li>
        </ol>
        <button type="button" class="btn-primary" id="shield-close">Pencereyi kapat</button>
      </section>`;
    if (tg.MainButton) tg.MainButton.hide();
    $('#shield-close').addEventListener('click', () => tg.close());
  }

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator) || !/^https?:$/.test(window.location.protocol)) return;
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('./service-worker.js').catch((err) => {
        console.warn('Service Worker kaydedilemedi:', err);
      });
    });
  }

  function init() {
    if (IN_TELEGRAM) {
      tg.ready();
      tg.expand();
      applyTheme();
      if (tg.onEvent) tg.onEvent('themeChanged', applyTheme);
      // initData yalnızca menü/inline butonundan açılışta dolu gelir; bu modda sendData çalışmaz.
      if (tg.initData) {
        renderWrongLaunch();
        return;
      }
      try {
        tg.setHeaderColor('secondary_bg_color');
        tg.setBackgroundColor('secondary_bg_color');
      } catch (err) {
        // Eski istemci sürümleri renk ayarını desteklemez.
      }
      if (tg.MainButton) {
        tg.MainButton.onClick(submit);
        tg.MainButton.show();
        $('#submit-fallback').hidden = true;
      }
    }

    if (!applySnapshot(Store.loadDraft())) applySnapshot({ duties: [DEFAULT_DUTY] });
    syncStaticInputs();
    renderMarket();
    renderNet();
    renderDuties();
    renderQueue();
    bindEvents();
    registerServiceWorker();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
