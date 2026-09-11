"""Uçtan uca duman testi: web.py'yi gerçekten başlatır ve bütün API akışlarını dener.

    python tools/smoke_test.py

Geçici bir klasörde boş veritabanı ve sabit piyasa verisiyle çalışır; canlı
veriye ve internete dokunmaz. Kurulum koduyla ilk yöneticiyi oluşturur, üyelik
ve şifre akışlarını, hesaplamayı (Excel/Telegram botuyla aynı sonuçlar), geçmişi,
istatistiği, CSV'yi, ayarları, yönetimi ve kişiler arası veri yalıtımını dener.
Beklenen çıktı `errors: 0` ve çıkış kodu 0'dır.
"""
import http.cookiejar
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding='utf-8')

REPO = Path(__file__).resolve().parent.parent
ADDON = REPO / 'gorev_maliyet'
WEB_PORT, INGRESS_PORT = 18102, 18099
BASE = f'http://127.0.0.1:{WEB_PORT}'
HEADERS = {'X-Requested-With': 'GorevMaliyet', 'Content-Type': 'application/json'}
TODAY = datetime.now(ZoneInfo('Europe/Istanbul')).date()

MARKET = {
    'eur_try': '48.1234',
    'eur_source_date': '10.09.2026',
    'fuel_prices': {
        'samsun': {
            'province_name': 'Samsun',
            'diesel_price_try_per_liter': '62.45',
            'gasoline_price_try_per_liter': '60.10',
            'source_date': TODAY.isoformat(),
            'source_name': 'Petrol Ofisi Samsun',
        },
    },
    'last_refresh_at': datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='seconds'),
}

errors = []


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, body=None, headers=None, raw=False):
        request = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                         headers=dict(HEADERS, **(headers or {})))
        try:
            with self.opener.open(request, timeout=60) as response:
                status, data, response_headers = response.status, response.read(), response.headers
        except urllib.error.HTTPError as e:
            status, data, response_headers = e.code, e.read(), e.headers
        if raw:
            return status, data, response_headers
        if 'json' in (response_headers.get('Content-Type') or ''):
            return status, json.loads(data or b'{}')
        return status, data


def check(name, condition, detail=''):
    if condition:
        print(f'  ok    {name}')
    else:
        errors.append((name, detail))
        print(f'  FAIL  {name}: {str(detail)[:400]}')


def duty(departure, arrival, liters):
    return {'departure': departure, 'arrival': arrival, 'fuel_liters': liters}


def main():
    work = Path(tempfile.mkdtemp(prefix='gorevmaliyet_smoke_'))
    (work / 'market_data.json').write_text(json.dumps(MARKET), encoding='utf-8')
    env = dict(os.environ, WEB_PORT=str(WEB_PORT), INGRESS_PORT=str(INGRESS_PORT), GOREV_MALIYET_DATA=str(work),
               MARKET_REFRESH='0', TZ='Europe/Istanbul', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    log_path = work / 'server.log'
    log_file = open(log_path, 'w', encoding='utf-8')
    proc = subprocess.Popen([sys.executable, '-u', str(ADDON / 'web.py')], cwd=str(ADDON), env=env,
                            stdout=log_file, stderr=subprocess.STDOUT)
    admin, second_admin, member, guest = Client(), Client(), Client(), Client()
    try:
        for _ in range(100):
            try:
                if guest.call('/health')[0] == 200:
                    break
            except OSError:
                time.sleep(0.2)

        print('\n== Sunucu ve statik dosyalar')
        check('health', guest.call('/health') == (200, {'status': 'ok'}))
        status, body, headers = guest.call('/', raw=True)
        check('index', status == 200 and 'Görev Maliyet'.encode('utf-8') in body)
        visible_text = body + guest.call('/static/app.js', raw=True)[1]
        check('arayüzde Excel ifadesi yok', b'excel' not in visible_text.lower())
        check('CSP başlığı', "default-src 'self'" in (headers.get('Content-Security-Policy') or ''))
        for name in ('app.js', 'calc.js', 'style.css', 'theme.js', 'icon.svg'):
            check(f'static/{name}', guest.call(f'/static/{name}', raw=True)[0] == 200)
        check('static yol dışına çıkamaz', guest.call('/static/../web.py', raw=True)[0] == 404)
        check('girişsiz bootstrap 401', guest.call('/api/bootstrap')[0] == 401)
        check('girişsiz hesaplama 401', guest.call('/api/calculate', {})[0] == 401)
        status, session = guest.call('/api/session')
        check('kurulum gerekli', status == 200 and session['setup_required'] is True and session['user'] is None)
        check('CSRF başlığı olmadan 403', guest.call('/api/login', {'username': 'x', 'password': 'y'},
                                                    headers={'X-Requested-With': ''})[0] == 403)

        print('\n== İlk kurulum')
        code = (work / 'setup_code').read_text(encoding='ascii')
        check('hatalı kurulum kodu 400', guest.call('/api/setup', {'code': '0000-0000', 'username': 'x',
                                                                  'display_name': 'X', 'password': 'Sifre12345'})[0] == 400)
        status, _ = admin.call('/api/setup', {'code': code, 'username': 'deneme', 'display_name': 'Deneme Yönetici',
                                              'password': 'DenemeSifre123!'})
        check('kurulum', status == 200)
        check('kurulum kodu silindi', not (work / 'setup_code').exists())
        check('ikinci kurulum 409', guest.call('/api/setup', {'code': code})[0] == 409)
        status, boot = admin.call('/api/bootstrap')
        check('bootstrap', status == 200 and boot['user']['is_admin'], boot)
        check('varsayılan sabit ayarlar', boot['settings'] == {'fuel_province': 'Samsun', 'solar_province': 'Samsun',
                                                               'monthly_salary': 105000.0}, boot['settings'])
        check('piyasa verisi', boot['market']['eur'] == 48.1234 and boot['market']['diesel'] == 62.45
              and boot['market']['ready'], boot['market'])
        provinces = boot['provinces']
        check('81 il, Türkçe sıralı', len(provinces) == 81 and provinces[0] == 'Adana'
              and provinces.index('Bursa') < provinces.index('Çanakkale') < provinces.index('Çorum') < provinces.index('Denizli')
              and provinces[-1] == 'Zonguldak', provinces[:5])
        check('son girdi yok', boot['last_inputs'] is None)

        print('\n== Hesaplama (Telegram botuyla doğrulanmış değerler)')
        status, single = admin.call('/api/calculate', {'duty_date': '2026-09-10', 'personnel': 4, 'fuel_type': 'diesel',
                                                       'duties': [duty('09:35', '19:25', 750)]})
        record = single.get('records', [{}])[0] if status == 200 else {}
        check('tek görev', status == 200 and single['summary'] is None and len(single['records']) == 1, single)
        check('tek görev toplam ₺53.953,82', record.get('total') == 53953.82, record)
        check('GÖRRAP satırı', record.get('gorrap_line') ==
              'MALİYET-1/9 SA 50 DA/1.380,21 TL/5.736,11 TL/0 TL/0 TL/46.837,50 TL/53.953,82 TL//', record.get('gorrap_line'))
        check('gündüz/gece Samsun 10.09', (record.get('day_minutes'), record.get('night_minutes')) == (558, 32), record)
        check('saatlik ve verim', record.get('hourly') == 5486.83 and record.get('efficiency') == 76.27, record)

        status, multi = admin.call('/api/calculate', {'duty_date': TODAY.isoformat(), 'personnel': 3, 'fuel_type': 'diesel',
                                                      'duties': [duty('22:00', '01:30', 10.5), duty('06:00', '08:15', 120)]})
        check('çoklu görev', status == 200 and len(multi.get('records', [])) == 2, multi)
        if status == 200:
            check('10,5 L × 62,45 = ₺655,73', multi['records'][0]['fuel_cost'] == 655.73, multi['records'][0])
            check('gece yarısı geçişi 3 SA 30 DA', multi['records'][0]['duration_text'] == '3 SA 30 DA')
            check('günlük toplam ₺11.472,42', multi['summary']['total'] == 11472.42, multi['summary'])
            check('tüm GÖRRAP satırları', len(multi['summary']['gorrap_lines']) == 2)

        previous_month = (TODAY.replace(day=1) - timedelta(days=3)).isoformat()
        status, gasoline = admin.call('/api/calculate', {'duty_date': previous_month, 'personnel': 2,
                                                         'fuel_type': 'gasoline', 'duties': [duty('10:00', '14:00', 200)]})
        check('benzin', status == 200 and gasoline['records'][0]['total'] == 13748.11
              and gasoline['records'][0]['fuel_kg'] == 149.0, gasoline)

        invalid = [
            ({'personnel': 4, 'duties': [duty('10:00', '10:00', 1)]}, 'aynı olamaz'),
            ({'personnel': 0, 'duties': [duty('10:00', '11:00', 1)]}, 'Personel'),
            ({'personnel': 4, 'duties': [duty('25:00', '11:00', 1)]}, 'Saat'),
            ({'personnel': 4, 'duties': [duty('10:00', '11:00', -5)]}, 'yakıt'),
            ({'personnel': 4, 'duties': [duty('10:00', '11:00', 1)] * 13}, 'en fazla'),
            ({'personnel': 4, 'duties': []}, 'En az bir'),
            ({'personnel': 4, 'duty_date': '2026-13-40', 'duties': [duty('10:00', '11:00', 1)]}, 'tarihi'),
        ]
        for payload, expected in invalid:
            status, response = admin.call('/api/calculate', payload)
            check(f'geçersiz veri reddedilir: {expected}', status == 400 and expected in response.get('error', ''), response)

        print('\n== Geçmiş, istatistik, CSV')
        status, history = admin.call('/api/history')
        check('geçmiş 4 kayıt', status == 200 and history['total'] == 4 and history['pages'] == 1, history)
        single_id = record.get('id')
        status, item = admin.call(f'/api/history/{single_id}')
        check('kayıt detayı', status == 200 and item['record']['id'] == single_id
              and item['inputs']['duties'] == [duty('09:35', '19:25', 750.0)], item)
        status, item = admin.call(f'/api/history/{multi["records"][1]["id"]}')
        check('çoklu kaydın günlük toplamı', status == 200 and item['batch_size'] == 2
              and item['batch_summary']['total'] == 11472.42, item)
        status, boot = admin.call('/api/bootstrap')
        check('son hesaplama girdisi', boot['last_inputs'] and boot['last_inputs']['fuel_type'] == 'gasoline', boot['last_inputs'])
        status, stats = admin.call('/api/stats')
        periods = {p['key']: p for p in stats.get('periods', [])}
        check('istatistik dönemleri', status == 200 and periods['all']['count'] == 4
              and periods['month']['count'] == 3 and periods['last_month']['count'] == 1, stats)
        check('istatistik dağılımı', stats.get('distribution') and stats['distribution']['basis'] == 'bu ay')
        status, body, headers = admin.call('/api/export', raw=True)
        text = body.decode('utf-8-sig') if status == 200 else ''
        check('CSV', status == 200 and body.startswith(b'\xef\xbb\xbf') and 'Kayıt No;Görev Tarihi' in text
              and 'MALİYET-1/9 SA 50 DA' in text and text.count('\r\n') == 5, text[:300])
        check('CSV dosya adı', 'attachment' in (headers.get('Content-Disposition') or ''))

        print('\n== Sabit ayarlar')
        status, saved = admin.call('/api/settings', {'fuel_province': 'İzmir', 'solar_province': 'Muğla',
                                                     'monthly_salary': '120.000'})
        check('ayarlar kaydedilir', status == 200 and saved['settings'] == {'fuel_province': 'İzmir', 'solar_province': 'Muğla',
                                                                            'monthly_salary': 120000.0}, saved)
        check('yeni il fiyatı henüz yok', status == 200 and saved['market']['diesel'] is None and not saved['market']['ready'])
        check('geçersiz il 400', admin.call('/api/settings', {'fuel_province': 'Atlantis', 'solar_province': 'Samsun',
                                                              'monthly_salary': '1'})[0] == 400)
        check('geçersiz maaş 400', admin.call('/api/settings', {'fuel_province': 'Samsun', 'solar_province': 'Samsun',
                                                                'monthly_salary': 'çok'})[0] == 400)
        admin.call('/api/settings', {'fuel_province': 'Samsun', 'solar_province': 'Samsun', 'monthly_salary': '105000'})

        print('\n== Üyelik, onay, şifre')
        registration_password = 'BasvuruKaydaGirmemeli123!'
        status, _ = member.call('/api/register', {'first_name': 'Aday', 'last_name': 'Kişi', 'email': 'aday@example.com',
                                                  'phone': '0532 123 45 67', 'position': 'uzman', 'username': 'aday',
                                                  'password': registration_password})
        check('üyelik başvurusu', status == 200)
        check('onaysız giriş engellenir', member.call('/api/login', {'username': 'aday', 'password': registration_password})[0] == 401)
        status, people = admin.call('/api/people')
        candidate = next((p for p in people.get('people', []) if p['username'] == 'aday'), None)
        check('başvuru listede bekliyor', candidate and candidate['approval_status'] == 'pending', people)
        status, approved = admin.call(f'/api/people/{candidate["id"]}', {'approval_status': 'approved'})
        check('başvuru onaylanır', status == 200 and approved['person']['is_active'])
        check('onaylı giriş', member.call('/api/login', {'username': 'aday', 'password': registration_password})[0] == 200)
        check('şifre talebi (var olan)', guest.call('/api/password-reset', {'identifier': 'aday@example.com'}) == (200, {'ok': True}))
        check('şifre talebi (olmayan) aynı yanıt', guest.call('/api/password-reset', {'identifier': 'yok@example.com'}) == (200, {'ok': True}))
        _, people = admin.call('/api/people')
        candidate = next(p for p in people['people'] if p['username'] == 'aday')
        check('talep yöneticide görünür', candidate['reset_pending'])
        admin.call(f'/api/people/{candidate["id"]}', {'password': 'AdayYeniSifre123!'})
        _, people = admin.call('/api/people')
        check('yeni şifre talebi kapatır', not next(p for p in people['people'] if p['username'] == 'aday')['reset_pending'])
        check('eski oturum şifre değişince kapanır', member.call('/api/bootstrap')[0] == 401)
        check('yeni şifreyle giriş', member.call('/api/login', {'username': 'aday', 'password': 'AdayYeniSifre123!'})[0] == 200)
        check('son yönetici yetkisini kaybedemez',
              admin.call(f'/api/people/{boot["user"]["id"]}', {'is_admin': False})[0] == 400)

        print('\n== Kişiler arası yalıtım ve yetki')
        check('başkasının kaydı 404', member.call(f'/api/history/{single_id}')[0] == 404)
        check('başkasının kaydı silinemez', member.call(f'/api/history/{single_id}/delete', {})[0] == 404)
        status, member_history = member.call('/api/history')
        check('üyenin geçmişi boş', status == 200 and member_history['total'] == 0)
        check('üye yönetimi göremez', member.call('/api/admin')[0] == 403 and member.call('/api/people')[0] == 403)
        check('Ingress başlığı 8102 portunda geçersiz',
              guest.call('/api/bootstrap', headers={'X-Remote-User-Name': 'deneme'})[0] == 401)
        status, own = member.call('/api/calculate', {'personnel': 2, 'fuel_type': 'diesel', 'duties': [duty('08:00', '09:00', 10)]})
        check('üye hesaplaması', status == 200)
        status, cleared = member.call('/api/history/clear', {})
        check('üye geçmişini temizler', status == 200 and cleared['removed'] == 1)
        _, history = admin.call('/api/history')
        check('yöneticinin kayıtları etkilenmez', history['total'] == 4)

        print('\n== Sorun bildirimi ve yönetim')
        issue_message = 'Duman testi sorun bildirimi'
        check('sorun bildirimi', member.call('/api/issues', {'message': issue_message})[0] == 200)
        check('çok kısa bildirim 400', member.call('/api/issues', {'message': 'a'})[0] == 400)
        status, admin_view = admin.call('/api/admin')
        issue = next((i for i in admin_view.get('issues', []) if i['message'] == issue_message), None)
        check('yönetim paneli', status == 200 and admin_view['overview']['calculations'] == 4
              and len(admin_view['overview']['trend']) == 7 and issue, admin_view)
        check('bildirim kapatılır', issue and admin.call(f'/api/admin/issues/{issue["id"]}/resolve', {})[0] == 200)
        check('kapalı bildirim tekrar kapatılamaz', issue and admin.call(f'/api/admin/issues/{issue["id"]}/resolve', {})[0] == 404)
        status, created = admin.call('/api/people', {'username': 'ikinci', 'display_name': 'İkinci Kişi',
                                                     'password': 'KaydaGirmemeli123!'})
        check('yönetici kişi ekler', status == 200 and created['person']['is_active'])

        print('\n== Kayıt silme, şifre değişikliği, giriş kilidi')
        check('kayıt silinir', admin.call(f'/api/history/{single_id}/delete', {})[0] == 200)
        check('silinen kayıt 404', admin.call(f'/api/history/{single_id}')[0] == 404)
        check('ikinci oturum', second_admin.call('/api/login', {'username': 'deneme', 'password': 'DenemeSifre123!'})[0] == 200)
        check('yanlış mevcut şifre 400', admin.call('/api/password', {'current': 'yanlis', 'new': 'DenemeYeniSifre123!'})[0] == 400)
        check('şifre değişikliği', admin.call('/api/password', {'current': 'DenemeSifre123!', 'new': 'DenemeYeniSifre123!'})[0] == 200)
        check('şifreyi değiştiren oturum açık kalır', admin.call('/api/bootstrap')[0] == 200)
        check('diğer cihazdaki oturum kapanır', second_admin.call('/api/bootstrap')[0] == 401)
        for _ in range(5):
            guest.call('/api/login', {'username': 'olmayan', 'password': 'yanlis'})
        check('5 hatalı denemeden sonra kilit', guest.call('/api/login', {'username': 'olmayan', 'password': 'yanlis'})[0] == 429)
        check('çıkış', admin.call('/api/logout', {})[0] == 200 and admin.call('/api/bootstrap')[0] == 401)

        print('\n== İşlem kayıtları')
        with sqlite3.connect(work / 'gorev_maliyet.db') as con:
            actions = dict(con.execute('SELECT action, COUNT(*) FROM activity_log GROUP BY action').fetchall())
            details = '\n'.join(row[0] or '' for row in con.execute('SELECT detail FROM activity_log'))
        for required in ('setup', 'login', 'logout', 'registration', 'password_reset_request', 'password_change',
                         'calculation', 'settings', 'export', 'history_delete', 'history_clear', 'issue_report',
                         'issue_resolve', 'person_create', 'person_update'):
            check(f'kayıt: {required}', actions.get(required), actions)
        check('parolalar kayda girmez', not any(secret in details for secret in (
            registration_password, 'AdayYeniSifre123!', 'DenemeSifre123!', 'KaydaGirmemeli123!')))
    finally:
        proc.terminate()
        proc.wait()
        log_file.close()
        log = log_path.read_text(encoding='utf-8')
        check('sunucu günlüğünde beklenmeyen hata yok', 'Traceback' not in log, log[-3000:])
        print('\n---- sunucu günlüğü (son satırlar) ----')
        print(log[-1500:])
    print('errors:', len(errors))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
