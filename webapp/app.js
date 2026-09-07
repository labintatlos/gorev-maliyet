// Telegram WebApp Görev Maliyet Hesaplayıcı

const tg = window.Telegram?.WebApp;

// Density constants
const DIESEL_DENSITY = 0.82;
const GASOLINE_DENSITY = 0.745;

// Haptic feedback helper
function haptic(type = 'light') {
  try {
    if (tg?.HapticFeedback) {
      if (type === 'success' || type === 'error' || type === 'warning') {
        tg.HapticFeedback.notificationOccurred(type);
      } else {
        tg.HapticFeedback.impactOccurred(type);
      }
    }
  } catch (e) {
    // Ignore haptic errors on unsupported platforms
  }
}

// Format number to 2 decimals
function formatNumber(num) {
  return Number(num).toLocaleString('tr-TR', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

// Current date as YYYY-MM-DD
function getTodayString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Current time as HH:MM
function getCurrentTimeString(dateObj = new Date()) {
  const hours = String(dateObj.getHours()).padStart(2, '0');
  const minutes = String(dateObj.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

// Calculate duration between HH:MM strings
function getDurationMinutes(depStr, arrStr) {
  if (!depStr || !arrStr) return 0;
  const [h1, m1] = depStr.split(':').map(Number);
  const [h2, m2] = arrStr.split(':').map(Number);
  
  let depTotal = h1 * 60 + m1;
  let arrTotal = h2 * 60 + m2;
  
  if (arrTotal < depTotal) {
    arrTotal += 24 * 60; // Next day
  }
  return arrTotal - depTotal;
}

function formatDurationText(dep, arr) {
  if (!dep || !arr) return '0 SA 00 DA';
  const totalMinutes = getDurationMinutes(dep, arr);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${h} SA ${String(m).padStart(2, '0')} DA`;
}

function getFuelKgText(liters) {
  const fuelType = document.querySelector('input[name="fuel_type"]:checked')?.value || 'diesel';
  const density = fuelType === 'gasoline' ? GASOLINE_DENSITY : DIESEL_DENSITY;
  const l = parseFloat(liters) || 0;
  const kg = (l * density).toFixed(1);
  return `Yaklaşık ~${formatNumber(kg)} kg`;
}

// Global State
let nextDutyId = 1;
let duties = [
  { id: 1, departure: '09:35', arrival: '19:25', fuel_liters: 750 }
];

// DOM Elements
const dutyDateInput = document.getElementById('duty-date');
const btnSubmit = document.getElementById('btn-submit');
const btnAddDuty = document.getElementById('btn-add-duty');

// Personnel helpers
function adjustPersonnel(delta) {
  haptic('selection');
  const input = document.getElementById('personnel');
  let val = (parseInt(input.value, 10) || 4) + delta;
  input.value = Math.max(1, Math.min(50, val));
  savePreferences();
}

function setPersonnel(val) {
  haptic('medium');
  document.getElementById('personnel').value = val;
  savePreferences();
}

// Duty Item Helpers
function setDutyFieldNow(id, field) {
  haptic('medium');
  const d = duties.find(item => item.id === id);
  if (!d) return;
  d[field] = getCurrentTimeString();
  renderDuties();
  savePreferences();
}

function adjustDutyTime(id, field, deltaMinutes) {
  haptic('selection');
  const d = duties.find(item => item.id === id);
  if (!d) return;
  let [h, m] = (d[field] || '12:00').split(':').map(Number);
  let total = (h * 60 + m + deltaMinutes) % (24 * 60);
  if (total < 0) total += 24 * 60;
  const newH = Math.floor(total / 60);
  const newM = total % 60;
  d[field] = `${String(newH).padStart(2, '0')}:${String(newM).padStart(2, '0')}`;
  renderDuties();
  savePreferences();
}

function updateDutyTime(id, field, value) {
  const d = duties.find(item => item.id === id);
  if (d) {
    d[field] = value;
    const durElem = document.getElementById(`calc-duration-${id}`);
    if (durElem) {
      durElem.textContent = formatDurationText(d.departure, d.arrival);
    }
    savePreferences();
  }
}

function updateDutyFuel(id, value) {
  const d = duties.find(item => item.id === id);
  if (d) {
    d.fuel_liters = value;
    const kgElem = document.getElementById(`fuel-kg-preview-${id}`);
    if (kgElem) {
      kgElem.textContent = getFuelKgText(value);
    }
    savePreferences();
  }
}

function adjustDutyFuel(id, delta) {
  haptic('selection');
  const d = duties.find(item => item.id === id);
  if (!d) return;
  let val = (parseFloat(d.fuel_liters) || 0) + delta;
  d.fuel_liters = Math.max(0, val);
  renderDuties();
  savePreferences();
}

function addDuty() {
  haptic('medium');
  nextDutyId++;
  const lastDuty = duties[duties.length - 1];
  let dep = lastDuty ? lastDuty.arrival : '12:00';
  let [h, m] = dep.split(':').map(Number);
  let totalArr = (h * 60 + m + 120) % (24 * 60);
  let arr = `${String(Math.floor(totalArr / 60)).padStart(2, '0')}:${String(totalArr % 60).padStart(2, '0')}`;
  
  duties.push({
    id: nextDutyId,
    departure: dep,
    arrival: arr,
    fuel_liters: 250
  });
  renderDuties();
  savePreferences();
}

function removeDuty(id) {
  haptic('warning');
  duties = duties.filter(item => item.id !== id);
  if (duties.length === 0) {
    nextDutyId = 1;
    duties.push({ id: 1, departure: '09:35', arrival: '19:25', fuel_liters: 750 });
  }
  renderDuties();
  savePreferences();
}

// Render dynamic duty cards
function renderDuties() {
  const container = document.getElementById('duties-container');
  if (!container) return;

  container.innerHTML = duties.map((duty, index) => {
    const dutyNum = index + 1;
    const isRemovable = duties.length > 1;
    return `
      <section class="section card duty-card" id="duty-card-${duty.id}">
        <div class="duty-card-header">
          <div class="section-title">⛵ ${dutyNum}. Görev</div>
          ${isRemovable ? `
            <button type="button" class="btn-remove-duty" onclick="removeDuty(${duty.id})">
              <span>✕ Görevi Sil</span>
            </button>
          ` : ''}
        </div>

        <div class="time-grid">
          <!-- Avara -->
          <div class="time-card">
            <div class="time-header">
              <span class="time-label">🚀 Avara (Kalkış)</span>
              <button type="button" class="btn-mini" onclick="setDutyFieldNow(${duty.id}, 'departure')">Şimdi</button>
            </div>
            <input type="time" class="time-input" value="${duty.departure}" onchange="updateDutyTime(${duty.id}, 'departure', this.value)" required>
            <div class="time-helpers">
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'departure', -5)">-5dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'departure', -15)">-15dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'departure', -60)">-1sa</button>
            </div>
            <div class="time-helpers" style="margin-top: 4px;">
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'departure', 5)">+5dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'departure', 15)">+15dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'departure', 60)">+1sa</button>
            </div>
          </div>

          <!-- Aborda -->
          <div class="time-card">
            <div class="time-header">
              <span class="time-label">⚓ Aborda (Varış)</span>
              <button type="button" class="btn-mini" onclick="setDutyFieldNow(${duty.id}, 'arrival')">Şimdi</button>
            </div>
            <input type="time" class="time-input" value="${duty.arrival}" onchange="updateDutyTime(${duty.id}, 'arrival', this.value)" required>
            <div class="time-helpers">
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'arrival', -5)">-5dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'arrival', -15)">-15dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'arrival', -60)">-1sa</button>
            </div>
            <div class="time-helpers" style="margin-top: 4px;">
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'arrival', 5)">+5dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'arrival', 15)">+15dk</button>
              <button type="button" class="helper-btn" onclick="adjustDutyTime(${duty.id}, 'arrival', 60)">+1sa</button>
            </div>
          </div>
        </div>

        <!-- Live Duration Display -->
        <div class="duration-badge">
          <span class="badge-icon">⏱</span>
          <span>${dutyNum}. Görev Süresi: <strong id="calc-duration-${duty.id}">${formatDurationText(duty.departure, duty.arrival)}</strong></span>
        </div>

        <hr class="divider">

        <!-- Fuel Liters -->
        <div class="stepper-row">
          <div class="stepper-label">
            <strong>Harcanan Yakıt</strong>
            <small id="fuel-kg-preview-${duty.id}">${getFuelKgText(duty.fuel_liters)}</small>
          </div>
          <div class="stepper-control fuel-stepper">
            <input type="number" class="step-input fuel-input" value="${duty.fuel_liters}" min="0" step="10" onchange="updateDutyFuel(${duty.id}, this.value)" oninput="updateDutyFuel(${duty.id}, this.value)">
            <span class="unit-tag">Litre</span>
          </div>
        </div>

        <div class="quick-nums" style="margin-bottom: 4px;">
          <button type="button" class="quick-num-btn" onclick="adjustDutyFuel(${duty.id}, -5)">−5L</button>
          <button type="button" class="quick-num-btn" onclick="adjustDutyFuel(${duty.id}, -15)">−15L</button>
          <button type="button" class="quick-num-btn" onclick="adjustDutyFuel(${duty.id}, -50)">−50L</button>
        </div>
        <div class="quick-nums">
          <button type="button" class="quick-num-btn" onclick="adjustDutyFuel(${duty.id}, 5)">+5L</button>
          <button type="button" class="quick-num-btn" onclick="adjustDutyFuel(${duty.id}, 15)">+15L</button>
          <button type="button" class="quick-num-btn" onclick="adjustDutyFuel(${duty.id}, 50)">+50L</button>
        </div>
      </section>
    `;
  }).join('');
}

// Save form values to localStorage
function savePreferences() {
  try {
    const data = {
      personnel: document.getElementById('personnel')?.value || '4',
      fuel_type: document.querySelector('input[name="fuel_type"]:checked')?.value || 'diesel',
      duties: duties,
    };
    localStorage.setItem('last_calc_prefs_v2', JSON.stringify(data));
  } catch (e) {
    // Ignore localStorage errors
  }
}

// Load saved values
function loadPreferences() {
  try {
    const raw = localStorage.getItem('last_calc_prefs_v2');
    if (raw) {
      const data = JSON.parse(raw);
      if (data.personnel) {
        const pInput = document.getElementById('personnel');
        if (pInput) pInput.value = data.personnel;
      }
      if (data.fuel_type) {
        const radio = document.querySelector(`input[name="fuel_type"][value="${data.fuel_type}"]`);
        if (radio) radio.checked = true;
      }
      if (data.duties && Array.isArray(data.duties) && data.duties.length > 0) {
        duties = data.duties;
        nextDutyId = Math.max(...duties.map(d => d.id || 1), 1);
      }
    }
  } catch (e) {
    // Ignore
  }
}

// Submit data to Telegram
function submitData() {
  const personnel = parseInt(document.getElementById('personnel').value, 10);
  const fuel_type = document.querySelector('input[name="fuel_type"]:checked')?.value || 'diesel';
  const duty_date = dutyDateInput.value || getTodayString();

  if (isNaN(personnel) || personnel < 1) {
    haptic('error');
    if (tg?.showAlert) tg.showAlert('Geçerli bir personel sayısı girin.');
    return;
  }

  for (let i = 0; i < duties.length; i++) {
    const d = duties[i];
    if (!d.departure || !d.arrival) {
      haptic('error');
      const msg = `Lütfen ${i + 1}. Görev için Avara ve Aborda saatlerini girin.`;
      if (tg?.showAlert) tg.showAlert(msg); else alert(msg);
      return;
    }
    const fl = parseFloat(d.fuel_liters);
    if (isNaN(fl) || fl < 0) {
      haptic('error');
      const msg = `Lütfen ${i + 1}. Görev için geçerli bir yakıt miktarı girin.`;
      if (tg?.showAlert) tg.showAlert(msg); else alert(msg);
      return;
    }
  }

  savePreferences();
  haptic('success');

  const payload = {
    duties: duties.map(d => ({
      departure: d.departure,
      arrival: d.arrival,
      fuel_liters: parseFloat(d.fuel_liters) || 0
    })),
    // Backward compatibility for single duty:
    departure: duties[0]?.departure || '',
    arrival: duties[0]?.arrival || '',
    fuel_liters: parseFloat(duties[0]?.fuel_liters) || 0,
    personnel,
    fuel_type,
    duty_date,
  };

  // If running inside Telegram WebApp
  if (tg && tg.sendData) {
    tg.sendData(JSON.stringify(payload));
    
    // sendData closes the app immediately. If it's still open, it means it failed
    setTimeout(() => {
      if (tg.showAlert) {
        tg.showAlert("Hata: Veri gönderilemedi!\n\nLütfen Mini Uygulamayı doğrudan sohbet klavyesinin altındaki '📱 Mini App Aç' butonuna basarak açın.");
      }
    }, 600);
  } else {
    // Standalone browser preview
    alert('Hesaplama Verisi Hazırlandı:\n' + JSON.stringify(payload, null, 2) + '\n\nTelegram içinde bu form bota doğrudan iletilir.');
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  // Telegram WebApp setup
  if (tg) {
    tg.ready();
    tg.expand();
    
    // FOOLPROOF SHIELD: If initData is present, it was NOT launched from a keyboard button.
    if (tg.initData) {
      document.body.innerHTML = `
        <div style="padding: 40px 20px; text-align: center;">
          <div style="font-size: 60px; margin-bottom: 20px;">⚠️</div>
          <h2 style="color: var(--text-color); margin-bottom: 15px;">Hatalı Giriş Saptandı</h2>
          <p style="color: var(--hint-color); font-size: 15px; line-height: 1.5; margin-bottom: 25px;">
            Telegram güvenlik kuralları gereği uygulamanın veri gönderebilmesi için <b>Klavye Butonu</b> üzerinden açılması zorunludur.
          </p>
          <div style="background: var(--secondary-bg-color); padding: 15px; border-radius: 12px; border: 1px solid var(--card-border);">
            <strong style="display:block; margin-bottom: 8px;">Nasıl Düzeltebilirim?</strong>
            1. Uygulamayı sağ üstten kapatın.<br><br>
            2. Sohbete <b>/start</b> yazın.<br><br>
            3. Ekranın en altındaki (klavye kısmındaki) devasa <b>📱 Mini App Aç</b> butonuna basın.
          </div>
        </div>
      `;
      if (tg.MainButton) tg.MainButton.hide();
      return;
    }

    // Set Telegram header color
    if (tg.setHeaderColor) {
      tg.setHeaderColor('secondary_bg_color');
    }

    // MainButton setup
    if (tg.MainButton) {
      tg.MainButton.setText('✅ GÖREVLERİ HESAPLA');
      tg.MainButton.show();
      tg.MainButton.onClick(submitData);
      
      // Hide HTML fallback button since we have the native MainButton
      const submitContainer = document.querySelector('.submit-container');
      if (submitContainer) submitContainer.style.display = 'none';
    }
  }

  // Set default date
  dutyDateInput.value = getTodayString();

  // Load preferences or defaults
  loadPreferences();
  renderDuties();

  // Add duty button listener
  if (btnAddDuty) {
    btnAddDuty.addEventListener('click', addDuty);
  }

  // Fuel type changes
  document.querySelectorAll('input[name="fuel_type"]').forEach(r => {
    r.addEventListener('change', () => {
      haptic('selection');
      renderDuties();
      savePreferences();
    });
  });

  // Quick Chips Listeners
  document.getElementById('btn-last-calc').addEventListener('click', () => {
    haptic('medium');
    loadPreferences();
    renderDuties();
  });

  document.getElementById('btn-sample-calc').addEventListener('click', () => {
    haptic('medium');
    duties = [{ id: 1, departure: '09:35', arrival: '19:25', fuel_liters: 750 }];
    nextDutyId = 1;
    document.getElementById('personnel').value = '4';
    document.getElementById('fuel-diesel').checked = true;
    renderDuties();
    savePreferences();
  });

  document.getElementById('btn-now-calc').addEventListener('click', () => {
    haptic('medium');
    const now = new Date();
    const fourHoursAgo = new Date(now.getTime() - (4 * 60 * 60 * 1000));
    duties = [{
      id: 1,
      departure: getCurrentTimeString(fourHoursAgo),
      arrival: getCurrentTimeString(now),
      fuel_liters: 500
    }];
    nextDutyId = 1;
    dutyDateInput.value = getTodayString();
    renderDuties();
    savePreferences();
  });

  // Submit button listener (for browsers/desktop)
  if (btnSubmit) {
    btnSubmit.addEventListener('click', submitData);
  }
});
