// Görev maliyeti hesap çekirdeği — calculator.py ile aynı formüller (Mini App önizlemesi için).
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.GorevCalc = api;
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DAY_MINUTES = 24 * 60;
  const HOURS_PER_MONTH = 720; // Excel: 30 gün × 24 saat
  const DEFAULT_DAILY_AMORTIZATION_EUR = 70;
  const DENSITY = { diesel: 0.82, gasoline: 0.745 };

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function parseTime(value) {
    const match = /^(\d{1,2})[:.](\d{2})(?::\d{2})?$/.exec(String(value == null ? '' : value).trim());
    if (!match) return null;
    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    if (hours > 23 || minutes > 59) return null;
    return hours * 60 + minutes;
  }

  function formatTime(totalMinutes) {
    const t = ((Math.round(totalMinutes) % DAY_MINUTES) + DAY_MINUTES) % DAY_MINUTES;
    return `${pad(Math.floor(t / 60))}:${pad(t % 60)}`;
  }

  function sanitizeTime(value, fallback) {
    const t = parseTime(value);
    return t === null ? fallback : formatTime(t);
  }

  // Excel MOD(Aborda − Avara, 1): gece yarısı geçişini destekler.
  function durationMinutes(departure, arrival) {
    const start = parseTime(departure);
    const end = parseTime(arrival);
    if (start === null || end === null) return 0;
    return (((end - start) % DAY_MINUTES) + DAY_MINUTES) % DAY_MINUTES;
  }

  function formatDuration(minutes) {
    const m = Math.max(0, Math.round(minutes));
    return `${Math.floor(m / 60)} SA ${pad(m % 60)} DA`;
  }

  // Aynı gün doğumu/batımı saatleri ertesi güne de uygulanır (önizleme yaklaşımı).
  function splitDaylight(departure, arrival, sunrise, sunset) {
    const start = parseTime(departure);
    const rise = parseTime(sunrise);
    const set = parseTime(sunset);
    if (start === null || rise === null || set === null) return null;
    const total = durationMinutes(departure, arrival);
    const end = start + total;
    let day = 0;
    for (const offset of [0, DAY_MINUTES]) {
      const from = Math.max(start, rise + offset);
      const to = Math.min(end, set + offset);
      if (to > from) day += to - from;
    }
    return { day, night: total - day };
  }

  function calculate(input) {
    const minutes = Math.max(0, Number(input.minutes) || 0);
    const hours = minutes / 60;
    const eur = Number(input.eur) || 0;
    const salary = Number(input.salary) || 0;
    const personnel = Number(input.personnel) || 0;
    const liters = Number(input.liters) || 0;
    const price = Number(input.price) || 0;
    const dailyAmortization = input.dailyAmortEur == null ? DEFAULT_DAILY_AMORTIZATION_EUR : Number(input.dailyAmortEur);

    const amortization = (dailyAmortization / 24) * eur * hours;
    const personnelCost = (salary / HOURS_PER_MONTH) * personnel * hours;
    const fuelCost = liters * price;
    const total = amortization + personnelCost + fuelCost;

    return {
      minutes,
      hours,
      amortization,
      personnelCost,
      fuelCost,
      total,
      fuelKg: liters * (DENSITY[input.fuelType] || DENSITY.diesel),
      hourly: hours > 0 ? total / hours : 0,
      efficiency: hours > 0 ? liters / hours : 0,
    };
  }

  // Python ROUND_HALF_UP ile uyum: 655.725 gibi değerlerde kayan nokta hatasına küçük pay.
  function roundHalfUp(value, decimals) {
    const factor = Math.pow(10, decimals);
    const v = Number(value) || 0;
    return (Math.sign(v) * Math.round(Math.abs(v) * factor + 1e-6)) / factor;
  }

  function formatMoney(value, decimals) {
    const d = decimals == null ? 2 : decimals;
    return roundHalfUp(value, d).toLocaleString('tr-TR', { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function formatNumber(value, maxDecimals) {
    const d = maxDecimals == null ? 2 : maxDecimals;
    return roundHalfUp(value, d).toLocaleString('tr-TR', { maximumFractionDigits: d });
  }

  function percent(part, whole) {
    return whole > 0 ? (part / whole) * 100 : 0;
  }

  return {
    DAY_MINUTES,
    DENSITY,
    parseTime,
    formatTime,
    sanitizeTime,
    durationMinutes,
    formatDuration,
    splitDaylight,
    calculate,
    roundHalfUp,
    formatMoney,
    formatNumber,
    percent,
  };
});
