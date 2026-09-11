"""Görev maliyeti iş kuralları: sabit ayarlar, hesaplama, geçmiş, istatistik, CSV.

Formüller calculator.py'dedir (Excel ile birebir). Bu modül Telegram botundaki
akışı web sitesine taşır: kullanıcı yalnızca sık değişen değerleri (tarih,
personel, yakıt türü, görevlerin avara/aborda saatleri ve yakıtı) gönderir;
maaş, akaryakıt ili ve güneş ili kişinin sabit ayarlarından, Euro kuru ve litre
fiyatı otomatik piyasa verisinden gelir.
"""

import csv
import io
import logging
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

import db
from calculator import (
    DAILY_AMORTIZATION_EUR,
    DIESEL_DENSITY_KG_PER_L,
    GASOLINE_DENSITY_KG_PER_L,
    HOURS_PER_MONTH,
    calculate,
    duration_minutes,
    format_tr,
    normalize_time,
    parse_decimal,
)
from provinces import PROVINCES, get_province
from solar_time import format_minutes, split_duty_by_daylight, sunrise_sunset

logger = logging.getLogger(__name__)

try:
    TZ = ZoneInfo(os.environ.get('TZ') or 'Europe/Istanbul')
except Exception:
    TZ = ZoneInfo('Europe/Istanbul')

MAX_DUTIES = 12
MAX_PERSONNEL = 500
MAX_FUEL_LITERS = Decimal('1000000')
MAX_SALARY = Decimal('100000000')
HISTORY_PAGE_SIZE = 15
TR_MONTHS = ('Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
             'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık')

FUEL_TYPES = {
    'diesel': {'label': 'Dizel', 'price_label': 'Motorin', 'density': DIESEL_DENSITY_KG_PER_L},
    'gasoline': {'label': 'Benzin', 'price_label': 'Benzin', 'density': GASOLINE_DENSITY_KG_PER_L},
}

DEFAULT_SETTINGS = {
    'fuel_province': 'Samsun',
    'solar_province': 'Samsun',
    'monthly_salary': Decimal('105000'),
}


class CostError(ValueError):
    """Kullanıcıya olduğu gibi gösterilebilecek hata."""


def today():
    return datetime.now(TZ).date()


def dec(value):
    """Kayıtlı kanonik (noktalı) sayı metnini Decimal'e çevirir.

    parse_decimal "655.725" gibi değerleri binlik ayırıcılı sanabildiği için
    veritabanındaki değerlerde bu fonksiyon kullanılır.
    """
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def num(value, places=2):
    """JSON için yuvarlanmış sayı (Python ROUND_HALF_UP)."""
    quantum = Decimal(1).scaleb(-places)
    return float(dec(value).quantize(quantum, rounding=ROUND_HALF_UP))


def fuel_type_of(value):
    return value if value in FUEL_TYPES else 'diesel'


# ── İller ────────────────────────────────────────────────────────────────

_TR_ORDER = 'abcçdefgğhıijklmnoöprsştuüvyz'


def _tr_sort_key(name):
    lowered = name.replace('I', 'ı').replace('İ', 'i').lower()
    return [(_TR_ORDER.index(ch) if ch in _TR_ORDER else 100 + ord(ch)) for ch in lowered]


def province_names():
    return sorted((p.name for p in PROVINCES), key=_tr_sort_key)


# ── Sabit ayarlar ────────────────────────────────────────────────────────

def get_settings(account_id):
    with db.session() as c:
        row = c.execute('SELECT fuel_province, solar_province, monthly_salary FROM user_settings WHERE account_id=?',
                        (account_id,)).fetchone()
    if not row:
        return dict(DEFAULT_SETTINGS)
    settings = {'monthly_salary': dec(row['monthly_salary'])}
    for key in ('fuel_province', 'solar_province'):
        try:
            settings[key] = get_province(str(row[key])).name
        except KeyError:
            settings[key] = DEFAULT_SETTINGS[key]
    return settings


def save_settings(account_id, fuel_province, solar_province, monthly_salary):
    try:
        fuel = get_province(str(fuel_province or '')).name
        solar = get_province(str(solar_province or '')).name
    except KeyError as exc:
        raise CostError('Listeden geçerli bir il seçin.') from exc
    try:
        salary = parse_decimal(monthly_salary if monthly_salary not in (None, '') else '')
    except ValueError as exc:
        raise CostError('Aylık maaşı sayı olarak yazın. Örnek: 105000') from exc
    if salary < 0 or salary > MAX_SALARY:
        raise CostError('Aylık maaş 0 ile 100.000.000 arasında olmalıdır.')
    with db.session() as c:
        c.execute('''INSERT INTO user_settings(account_id,fuel_province,solar_province,monthly_salary,updated_at)
                     VALUES(?,?,?,?,?)
                     ON CONFLICT(account_id) DO UPDATE SET
                        fuel_province=excluded.fuel_province, solar_province=excluded.solar_province,
                        monthly_salary=excluded.monthly_salary, updated_at=excluded.updated_at''',
                  (account_id, fuel, solar, str(salary), db.now_iso()))
    return get_settings(account_id)


def settings_view(settings):
    return {
        'fuel_province': settings['fuel_province'],
        'solar_province': settings['solar_province'],
        'monthly_salary': num(settings['monthly_salary']),
    }


def configured_fuel_provinces():
    with db.session() as c:
        rows = c.execute('SELECT DISTINCT fuel_province FROM user_settings').fetchall()
    names = {str(row[0]) for row in rows if row[0]}
    names.add(DEFAULT_SETTINGS['fuel_province'])
    return sorted(names, key=_tr_sort_key)


# ── Piyasa verisi ────────────────────────────────────────────────────────

def market_view(store, account_id):
    settings = get_settings(account_id)
    snap = store.get()
    fuel = snap.province_snapshot(settings['fuel_province'])
    sunrise = sunset = None
    try:
        rise, set_ = sunrise_sunset(today(), province=settings['solar_province'])
        sunrise, sunset = f'{rise:%H:%M}', f'{set_:%H:%M}'
    except Exception:
        logger.exception('Gün doğumu/batımı hesaplanamadı')
    diesel = fuel.diesel_decimal if fuel else None
    gasoline = fuel.gasoline_decimal if fuel else None
    return {
        'eur': num(snap.eur_decimal, 4) if snap.eur_decimal is not None else None,
        'eur_date': snap.eur_source_date,
        'diesel': num(diesel) if diesel is not None else None,
        'gasoline': num(gasoline) if gasoline is not None else None,
        'fuel_date': fuel.source_date if fuel else None,
        'fuel_province': settings['fuel_province'],
        'solar_province': settings['solar_province'],
        'sunrise': sunrise,
        'sunset': sunset,
        'monthly_salary': num(settings['monthly_salary']),
        'last_refresh_at': snap.last_refresh_at,
        'ready': snap.eur_decimal is not None and diesel is not None and gasoline is not None,
    }


def constants_view():
    return {
        'daily_amortization_eur': num(DAILY_AMORTIZATION_EUR),
        'hourly_amortization_eur': num(DAILY_AMORTIZATION_EUR / Decimal(24), 4),
        'hours_per_month': int(HOURS_PER_MONTH),
        'density': {key: float(item['density']) for key, item in FUEL_TYPES.items()},
    }


def ensure_price(store, fuel_type, province):
    """Önbellekteki Euro ve litre fiyatını döndürür; eksikse bir kez yenilemeyi dener."""
    snap = store.get()
    price = snap.price_for(fuel_type, province)
    if snap.eur_decimal is None or price is None:
        try:
            store.refresh([province])
        except Exception:
            logger.exception('Hesap öncesi piyasa verisi yenilenemedi')
        snap = store.get()
        price = snap.price_for(fuel_type, province)
    if snap.eur_decimal is None or price is None:
        return None, None
    return snap.eur_decimal, price


# ── Hesaplama ────────────────────────────────────────────────────────────

def parse_payload(payload):
    """Hesap formunu doğrular: (personel, yakıt türü, görev tarihi, görevler)."""
    if not isinstance(payload, dict):
        raise CostError('Veri biçimi tanınmadı.')
    try:
        personnel = int(payload.get('personnel'))
    except (TypeError, ValueError) as exc:
        raise CostError('Personel sayısı geçersiz.') from exc
    if not 1 <= personnel <= MAX_PERSONNEL:
        raise CostError(f'Personel sayısı 1 ile {MAX_PERSONNEL} arasında olmalıdır.')

    fuel_type = fuel_type_of(str(payload.get('fuel_type') or 'diesel').strip().lower())

    duty_date = today()
    raw_date = str(payload.get('duty_date') or '').strip()
    if raw_date:
        try:
            duty_date = date.fromisoformat(raw_date[:10])
        except ValueError as exc:
            raise CostError('Görev tarihi geçersiz.') from exc

    raw_duties = payload.get('duties')
    if not isinstance(raw_duties, list) or not raw_duties:
        raise CostError('En az bir görev girilmelidir.')
    if len(raw_duties) > MAX_DUTIES:
        raise CostError(f'Tek seferde en fazla {MAX_DUTIES} görev hesaplanabilir.')

    duties = []
    for index, raw in enumerate(raw_duties, start=1):
        label = f'{index}. görev'
        if not isinstance(raw, dict):
            raise CostError(f'{label}: veri biçimi tanınmadı.')
        try:
            departure = normalize_time(str(raw.get('departure') or ''))
            arrival = normalize_time(str(raw.get('arrival') or ''))
            fuel_raw = raw.get('fuel_liters')
            fuel = parse_decimal(fuel_raw if fuel_raw not in (None, '') else 0)
        except ValueError as exc:
            raise CostError(f'{label}: {exc}') from exc
        if fuel < 0 or fuel > MAX_FUEL_LITERS:
            raise CostError(f'{label}: yakıt miktarı geçersiz.')
        if duration_minutes(departure, arrival) == 0:
            raise CostError(f'{label}: Avara ve Aborda saatleri aynı olamaz.')
        duties.append({'departure': departure, 'arrival': arrival, 'fuel_liters': fuel})
    return personnel, fuel_type, duty_date, duties


def calculate_and_save(store, account_id, payload):
    personnel, fuel_type, duty_date, duties = parse_payload(payload)
    settings = get_settings(account_id)
    eur, price = ensure_price(store, fuel_type, settings['fuel_province'])
    if price is None:
        raise CostError(
            f'Euro kuru veya {settings["fuel_province"]} {FUEL_TYPES[fuel_type]["price_label"].lower()} fiyatı '
            'henüz alınamadı. Ayarlar sayfasındaki Otomatik veriler bölümünden yenilemeyi deneyin.')

    density = FUEL_TYPES[fuel_type]['density']
    batch_id = uuid.uuid4().hex
    created_at = datetime.now(TZ).isoformat(timespec='seconds')
    ids = []
    with db.session() as c:
        for duty in duties:
            result = calculate(
                departure=duty['departure'],
                arrival=duty['arrival'],
                eur_try=eur,
                monthly_salary_try=settings['monthly_salary'],
                personnel_count=personnel,
                fuel_liters=duty['fuel_liters'],
                fuel_price_try_per_liter=price,
                fuel_density_kg_per_l=density,
            )
            split = split_duty_by_daylight(result.departure, result.arrival, basis_date=duty_date,
                                           province=settings['solar_province'])
            cur = c.execute('''INSERT INTO calculations(
                    account_id, batch_id, created_at, duty_date, departure, arrival, duration_minutes,
                    day_minutes, night_minutes, personnel, fuel_type, fuel_liters, fuel_province,
                    solar_province, fuel_price, eur_rate, monthly_salary, amortization_cost,
                    personnel_cost, fuel_cost, total_cost, gorrap_line)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                account_id, batch_id, created_at, duty_date.isoformat(), result.departure, result.arrival,
                result.duration_minutes, split.day_minutes, split.night_minutes, personnel, fuel_type,
                str(result.fuel_liters), settings['fuel_province'], settings['solar_province'], str(price),
                str(eur), str(settings['monthly_salary']), str(result.amortization_cost_try),
                str(result.personnel_cost_try), str(result.fuel_cost_try), str(result.total_cost_try),
                result.gorrap_line))
            ids.append(cur.lastrowid)
        rows = c.execute(f'SELECT * FROM calculations WHERE id IN ({",".join("?" * len(ids))}) ORDER BY id',
                         ids).fetchall()
    return {
        'records': [record_view(row) for row in rows],
        'summary': summary_view(rows) if len(rows) > 1 else None,
    }


def record_view(row):
    fuel_type = fuel_type_of(row['fuel_type'])
    minutes = int(row['duration_minutes'])
    hours = Decimal(minutes) / Decimal(60)
    liters = dec(row['fuel_liters'])
    total = dec(row['total_cost'])
    return {
        'id': row['id'],
        'batch_id': row['batch_id'],
        'created_at': row['created_at'],
        'duty_date': row['duty_date'],
        'departure': row['departure'],
        'arrival': row['arrival'],
        'duration_minutes': minutes,
        'duration_text': format_minutes(minutes),
        'day_minutes': int(row['day_minutes']),
        'night_minutes': int(row['night_minutes']),
        'day_text': format_minutes(row['day_minutes']),
        'night_text': format_minutes(row['night_minutes']),
        'personnel': int(row['personnel']),
        'fuel_type': fuel_type,
        'fuel_label': FUEL_TYPES[fuel_type]['label'],
        'fuel_liters': num(liters),
        'fuel_kg': num(liters * FUEL_TYPES[fuel_type]['density']),
        'fuel_price': num(row['fuel_price']),
        'fuel_province': row['fuel_province'],
        'solar_province': row['solar_province'],
        'eur_rate': num(row['eur_rate'], 4),
        'monthly_salary': num(row['monthly_salary']),
        'amortization': num(row['amortization_cost']),
        'personnel_cost': num(row['personnel_cost']),
        'fuel_cost': num(row['fuel_cost']),
        'total': num(total),
        'hourly': num(total / hours) if hours > 0 else 0,
        'efficiency': num(liters / hours) if hours > 0 else 0,
        'gorrap_line': row['gorrap_line'],
    }


def _summarize(rows):
    zero = Decimal('0')
    summary = {'count': 0, 'minutes': 0, 'day_minutes': 0, 'night_minutes': 0, 'fuel_liters': zero,
               'amortization': zero, 'personnel_cost': zero, 'fuel_cost': zero, 'total': zero}
    for row in rows:
        summary['count'] += 1
        summary['minutes'] += int(row['duration_minutes'])
        summary['day_minutes'] += int(row['day_minutes'])
        summary['night_minutes'] += int(row['night_minutes'])
        summary['fuel_liters'] += dec(row['fuel_liters'])
        summary['amortization'] += dec(row['amortization_cost'])
        summary['personnel_cost'] += dec(row['personnel_cost'])
        summary['fuel_cost'] += dec(row['fuel_cost'])
        summary['total'] += dec(row['total_cost'])
    return summary


def summary_view(rows):
    s = _summarize(rows)
    return {
        'count': s['count'],
        'duration_minutes': s['minutes'],
        'duration_text': format_minutes(s['minutes']),
        'day_text': format_minutes(s['day_minutes']),
        'night_text': format_minutes(s['night_minutes']),
        'fuel_liters': num(s['fuel_liters']),
        'amortization': num(s['amortization']),
        'personnel_cost': num(s['personnel_cost']),
        'fuel_cost': num(s['fuel_cost']),
        'total': num(s['total']),
        'average': num(s['total'] / s['count']) if s['count'] else 0,
        'gorrap_lines': [row['gorrap_line'] for row in rows],
    }


def last_inputs(account_id):
    """Son gönderilen formu (aynı gönderimdeki bütün görevlerle) döndürür."""
    with db.session() as c:
        last = c.execute('SELECT batch_id FROM calculations WHERE account_id=? ORDER BY id DESC LIMIT 1',
                         (account_id,)).fetchone()
        if not last:
            return None
        rows = c.execute('SELECT * FROM calculations WHERE account_id=? AND batch_id=? ORDER BY id',
                         (account_id, last['batch_id'])).fetchall()
    return inputs_of(rows)


def inputs_of(rows):
    first = rows[0]
    return {
        'duty_date': first['duty_date'],
        'personnel': int(first['personnel']),
        'fuel_type': fuel_type_of(first['fuel_type']),
        'duties': [{'departure': r['departure'], 'arrival': r['arrival'], 'fuel_liters': num(r['fuel_liters'])}
                   for r in rows],
    }


# ── Geçmiş ───────────────────────────────────────────────────────────────

def history_page(account_id, page):
    with db.session() as c:
        total = c.execute('SELECT COUNT(*) FROM calculations WHERE account_id=?', (account_id,)).fetchone()[0]
        pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        page = max(0, min(int(page), pages - 1))
        rows = c.execute('SELECT * FROM calculations WHERE account_id=? ORDER BY id DESC LIMIT ? OFFSET ?',
                         (account_id, HISTORY_PAGE_SIZE, page * HISTORY_PAGE_SIZE)).fetchall()
    return {'items': [record_view(r) for r in rows], 'page': page, 'pages': pages, 'total': total}


def history_item(account_id, item_id):
    with db.session() as c:
        row = c.execute('SELECT * FROM calculations WHERE account_id=? AND id=?', (account_id, int(item_id))).fetchone()
        if not row:
            return None
        batch = c.execute('SELECT * FROM calculations WHERE account_id=? AND batch_id=? ORDER BY id',
                          (account_id, row['batch_id'])).fetchall()
    return {
        'record': record_view(row),
        'inputs': inputs_of([row]),
        'batch_size': len(batch),
        'batch_summary': summary_view(batch) if len(batch) > 1 else None,
    }


def delete_item(account_id, item_id):
    with db.session() as c:
        return c.execute('DELETE FROM calculations WHERE account_id=? AND id=?',
                         (account_id, int(item_id))).rowcount > 0


def clear_history(account_id):
    with db.session() as c:
        return c.execute('DELETE FROM calculations WHERE account_id=?', (account_id,)).rowcount


def _csv_number(value, places=2):
    # Türkçe Excel'in sayı olarak tanıması için binlik ayırıcısız, virgüllü ondalık.
    return format_tr(dec(value), places).replace('.', '')


def history_csv(account_id):
    with db.session() as c:
        rows = c.execute('SELECT * FROM calculations WHERE account_id=? ORDER BY id', (account_id,)).fetchall()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
    writer.writerow([
        'Kayıt No', 'Görev Tarihi', 'Kayıt Zamanı', 'Avara', 'Aborda', 'Süre', 'Gündüz', 'Gece',
        'Personel', 'Yakıt Türü', 'Yakıt (L)', 'Litre Fiyatı (TL)', 'Akaryakıt İli', 'Güneş İli',
        'Euro (TL)', 'Aylık Maaş (TL)', 'Amortisman (TL)', 'Personel Maliyeti (TL)',
        'Yakıt Maliyeti (TL)', 'Toplam (TL)', 'GÖRRAP',
    ])
    for row in rows:
        created = row['created_at']
        try:
            created = datetime.fromisoformat(created).strftime('%d.%m.%Y %H:%M')
        except ValueError:
            pass
        writer.writerow([
            row['id'],
            date.fromisoformat(row['duty_date']).strftime('%d.%m.%Y'),
            created,
            row['departure'],
            row['arrival'],
            format_minutes(row['duration_minutes']),
            format_minutes(row['day_minutes']),
            format_minutes(row['night_minutes']),
            row['personnel'],
            FUEL_TYPES[fuel_type_of(row['fuel_type'])]['label'],
            _csv_number(row['fuel_liters']),
            _csv_number(row['fuel_price']),
            row['fuel_province'],
            row['solar_province'],
            _csv_number(row['eur_rate'], 4),
            _csv_number(row['monthly_salary']),
            _csv_number(row['amortization_cost']),
            _csv_number(row['personnel_cost']),
            _csv_number(row['fuel_cost']),
            _csv_number(row['total_cost']),
            row['gorrap_line'],
        ])
    # BOM, Excel'in Türkçe karakterleri doğru okumasını sağlar.
    return ('\ufeff' + buffer.getvalue()).encode('utf-8'), len(rows)


# ── İstatistik ───────────────────────────────────────────────────────────

def month_bounds(day):
    start = day.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return start, end


def _rows_between(rows, start, end):
    return [row for row in rows if start <= date.fromisoformat(row['duty_date']) <= end]


def _period(key, title, rows):
    s = _summarize(rows)
    return {
        'key': key,
        'title': title,
        'count': s['count'],
        'duration_text': format_minutes(s['minutes']),
        'fuel_liters': num(s['fuel_liters']),
        'amortization': num(s['amortization']),
        'personnel_cost': num(s['personnel_cost']),
        'fuel_cost': num(s['fuel_cost']),
        'total': num(s['total']),
        'average': num(s['total'] / s['count']) if s['count'] else 0,
        '_total': s['total'],
    }


def stats(account_id):
    with db.session() as c:
        rows = c.execute('SELECT * FROM calculations WHERE account_id=? ORDER BY id', (account_id,)).fetchall()
    day = today()
    month_start, month_end = month_bounds(day)
    prev_start, prev_end = month_bounds(month_start - timedelta(days=1))
    this_month = _period('month', f'Bu ay · {TR_MONTHS[day.month - 1]} {day.year}',
                         _rows_between(rows, month_start, month_end))
    last_week = _period('week', 'Son 7 gün', _rows_between(rows, day - timedelta(days=6), day))
    last_month = _period('last_month', f'Geçen ay · {TR_MONTHS[prev_start.month - 1]} {prev_start.year}',
                         _rows_between(rows, prev_start, prev_end))
    overall = _period('all', 'Tüm zamanlar', rows)

    change = None
    if this_month['count'] and last_month['_total'] > 0:
        change = num((this_month['_total'] - last_month['_total']) / last_month['_total'] * 100, 1)
    basis = this_month if this_month['count'] else overall
    periods = [this_month, last_week, last_month, overall]
    for period in periods:
        period.pop('_total')
    return {
        'periods': periods,
        'change_vs_last_month': change,
        'distribution': {
            'basis': 'bu ay' if basis is this_month else 'tüm zamanlar',
            'amortization': basis['amortization'],
            'personnel_cost': basis['personnel_cost'],
            'fuel_cost': basis['fuel_cost'],
            'total': basis['total'],
        } if basis['count'] else None,
    }


# ── Yönetim ──────────────────────────────────────────────────────────────

def admin_overview():
    day = today()
    start = day - timedelta(days=6)
    with db.session() as c:
        totals = c.execute('SELECT COUNT(*) AS n, COUNT(DISTINCT account_id) AS people FROM calculations').fetchone()
        today_count = c.execute("SELECT COUNT(*) FROM calculations WHERE substr(created_at,1,10)=?",
                                (day.isoformat(),)).fetchone()[0]
        accounts = c.execute('''SELECT
                SUM(CASE WHEN approval_status='approved' AND is_active=1 THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN approval_status='pending' THEN 1 ELSE 0 END) AS pending
            FROM web_accounts''').fetchone()
        trend_rows = c.execute('''SELECT substr(created_at,1,10) AS day, COUNT(*) AS n FROM calculations
                                  WHERE substr(created_at,1,10) >= ? GROUP BY day''', (start.isoformat(),)).fetchall()
        people = c.execute('''SELECT w.id, w.display_name, w.username, w.last_login,
                                     COUNT(k.id) AS calculations, MAX(k.created_at) AS last_calculation
                              FROM web_accounts w LEFT JOIN calculations k ON k.account_id = w.id
                              WHERE w.approval_status='approved'
                              GROUP BY w.id ORDER BY calculations DESC, w.display_name COLLATE NOCASE''').fetchall()
    by_day = {row['day']: row['n'] for row in trend_rows}
    return {
        'calculations': totals['n'],
        'calculating_people': totals['people'],
        'today': today_count,
        'active_accounts': accounts['active'] or 0,
        'pending_accounts': accounts['pending'] or 0,
        'trend': [{'day': (start + timedelta(days=i)).isoformat(),
                   'count': by_day.get((start + timedelta(days=i)).isoformat(), 0)} for i in range(7)],
        'people': [dict(row) for row in people],
    }
