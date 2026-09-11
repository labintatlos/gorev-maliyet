"""Görev Maliyet Hesaplayıcı — web sunucusu.

İki dinleyici açılır:

- 8099 (Ingress): Home Assistant yan menüsündeki panel. `X-Remote-User-Name`
  başlığına yalnızca Supervisor'ın adresinden gelen istekte güvenilir. Bu
  panelden bir kez site şifresiyle giren kişi orada bir daha şifre görmez.
- 8102 (web sitesi): ev ağı ve KeenDNS. Kimlik yalnızca kullanıcı adı ve
  şifreyle verilen oturum çerezinden gelir; başlıklara hiç bakılmaz.

Piyasa verisi (TCMB Euro, Petrol Ofisi il fiyatları) açılışta ve her gün
17:00'de arka planda yenilenir. Yalnızca standart kütüphane kullanılır.
"""

import json
import logging
import os
import re
import sys
import threading
import time as time_module
from datetime import datetime, time, timedelta
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import accounts
import costs
import db
from market_data import MarketDataStore

logger = logging.getLogger('web')

STATIC_DIR = Path(__file__).parent / 'static'
STATIC_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.svg': 'image/svg+xml',
}
SUPERVISOR_IP = os.environ.get('INGRESS_TRUSTED_IP', '172.30.32.2')
MAX_BODY_BYTES = 64 * 1024
REQUEST_HEADER = 'GorevMaliyet'
AUTO_REFRESH_AT = time(17, 0)

throttle = accounts.LoginThrottle()
MARKET = MarketDataStore(db.DATA_DIR / 'market_data.json')


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def refresh_in_background(provinces):
    if os.environ.get('MARKET_REFRESH', '1') == '0':
        return

    def run():
        try:
            MARKET.refresh(provinces)
        except Exception:
            logger.exception('Piyasa verisi arka planda yenilenemedi')
    threading.Thread(target=run, name='market-refresh', daemon=True).start()


def market_loop():
    """Açılışta ve her gün 17:00'de (Türkiye saati) kullanılan illerin fiyatlarını yeniler."""
    while True:
        try:
            provinces = costs.configured_fuel_provinces()
            result = MARKET.refresh(provinces)
            logger.info('Piyasa verisi kontrol edildi. EUR=%s, iller=%s', result['snapshot'].eur_try,
                        ', '.join(provinces))
        except Exception:
            logger.exception('Piyasa verisi güncellemesi beklenmeyen hata verdi')
        now = datetime.now(costs.TZ)
        next_run = datetime.combine(now.date(), AUTO_REFRESH_AT, tzinfo=costs.TZ)
        if now >= next_run:
            next_run += timedelta(days=1)
        logger.info('Bir sonraki piyasa verisi güncellemesi: %s', next_run.isoformat(timespec='minutes'))
        time_module.sleep(max(1.0, (next_run - now).total_seconds()))


# ── HTTP ─────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = 'GorevMaliyet'
    sys_version = ''
    protocol_version = 'HTTP/1.1'
    ingress = False
    # Yarım bırakılan bağlantı bir iş parçacığını sonsuza dek tutmasın.
    timeout = 60

    def log_message(self, fmt, *args):
        pass

    # Kimlik
    def client_ip(self):
        return self.client_address[0]

    def ha_user(self):
        if not self.ingress or self.client_ip() != SUPERVISOR_IP:
            return None
        return (self.headers.get('X-Remote-User-Name') or '').strip() or None

    def cookie(self, name):
        try:
            jar = SimpleCookie(self.headers.get('Cookie') or '')
        except CookieError:
            return None
        return jar[name].value if name in jar else None

    def identity(self):
        linked = accounts.find_by_ha_user(self.ha_user())
        if linked:
            return linked, 'ingress'
        token = self.cookie(accounts.COOKIE_NAME)
        account = accounts.account_from_token(token) if token else None
        return (account, 'cookie') if account else (None, None)

    def require_account(self, admin=False):
        account, _ = self.identity()
        if not account:
            raise ApiError(401, 'Oturum açmanız gerekiyor.')
        if admin and not account['is_admin']:
            raise ApiError(403, 'Bu işlem için yönetici yetkisi gerekiyor.')
        return account

    # Yanıtlar
    def security_headers(self):
        csp = "default-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; object-src 'none'"
        if not self.ingress:
            csp += "; frame-ancestors 'none'"
            # Tarayıcı bunu yalnızca HTTPS'te dikkate alır: KeenDNS adresi bir
            # kez https ile açılınca bir daha düz http ile açılmaz.
            self.send_header('Strict-Transport-Security', 'max-age=31536000')
        self.send_header('Content-Security-Policy', csp)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')

    def send_body(self, status, body, content_type, cookies=(), cache='no-store', extra_headers=()):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        for name, value in extra_headers:
            self.send_header(name, value)
        for cookie in cookies:
            self.send_header('Set-Cookie', cookie)
        self.security_headers()
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def send_json(self, status, payload, cookies=()):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_body(status, body, 'application/json; charset=utf-8', cookies)

    def cookie_flags(self):
        flags = 'Path=/; HttpOnly; SameSite=Lax'
        # KeenDNS tüneli X-Forwarded-Proto göndermez. Tarayıcının POST
        # isteğine kendiliğinden eklediği Origin, sayfanın https ile açıldığını
        # gösterir; o durumda çerez düz http üzerinden hiç gönderilmez.
        origin = (self.headers.get('Origin') or '').lower()
        if origin.startswith('https://') or (self.headers.get('X-Forwarded-Proto') or '').lower() == 'https':
            flags += '; Secure'
        return flags

    def session_cookie(self, account, remember):
        token, max_age = accounts.issue_token(account, remember)
        cookie = f'{accounts.COOKIE_NAME}={token}; {self.cookie_flags()}'
        if max_age:
            cookie += f'; Max-Age={max_age}'
        return cookie

    def read_json(self):
        # Başka bir sitenin tarayıcı üzerinden istek atmasını (CSRF) engeller:
        # bu başlık ancak aynı kökenden çalışan betik tarafından eklenebilir.
        if self.headers.get('X-Requested-With') != REQUEST_HEADER:
            self.close_connection = True
            raise ApiError(403, 'Geçersiz istek.')
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True
            raise ApiError(400, 'Geçersiz istek.')
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            raise ApiError(413, 'İstek çok büyük.')
        try:
            data = json.loads(self.rfile.read(length) or b'{}')
        except ValueError:
            raise ApiError(400, 'Geçersiz istek.')
        if not isinstance(data, dict):
            raise ApiError(400, 'Geçersiz istek.')
        return data

    # Yönlendirme
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.dispatch(self.route_get)

    def do_POST(self):
        self.dispatch(self.route_post)

    def dispatch(self, route):
        parts = urlsplit(self.path)
        try:
            route(parts.path, parse_qs(parts.query))
        except ApiError as e:
            self.send_json(e.status, {'error': e.message})
        except (accounts.AccountError, costs.CostError) as e:
            self.send_json(400, {'error': str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            logger.exception('İstek işlenemedi: %s %s', self.command, parts.path)
            try:
                self.send_json(500, {'error': 'Sunucuda beklenmeyen bir hata oluştu.'})
            except Exception:
                pass

    def route_get(self, path, query):
        if path in ('/', '/index.html'):
            return self.send_static('index.html')
        if path.startswith('/static/'):
            return self.send_static(path[len('/static/'):])
        if path == '/health':
            return self.send_json(200, {'status': 'ok'})
        if path == '/api/session':
            account, via = self.identity()
            return self.send_json(200, {
                'setup_required': accounts.setup_required(),
                'ingress': bool(self.ha_user()),
                'user': dict(accounts.public(account), via=via) if account else None,
            })

        account = self.require_account()
        if path == '/api/bootstrap':
            return self.send_json(200, {
                'user': dict(accounts.public(account), via=self.identity()[1]),
                'settings': costs.settings_view(costs.get_settings(account['id'])),
                'market': costs.market_view(MARKET, account['id']),
                'constants': costs.constants_view(),
                'provinces': costs.province_names(),
                'last_inputs': costs.last_inputs(account['id']),
            })
        if path == '/api/market':
            return self.send_json(200, {'market': costs.market_view(MARKET, account['id'])})
        if path == '/api/history':
            try:
                page = int((query.get('page') or ['0'])[0])
            except ValueError:
                page = 0
            return self.send_json(200, costs.history_page(account['id'], page))
        match = re.fullmatch(r'/api/history/(\d+)', path)
        if match:
            item = costs.history_item(account['id'], int(match.group(1)))
            if not item:
                raise ApiError(404, 'Kayıt bulunamadı.')
            return self.send_json(200, item)
        if path == '/api/stats':
            return self.send_json(200, costs.stats(account['id']))
        if path == '/api/export':
            body, count = costs.history_csv(account['id'])
            db.log_activity(account['id'], 'export', f'{count} kayıt')
            filename = f'gorev_maliyet_{datetime.now(costs.TZ):%Y%m%d_%H%M}.csv'
            return self.send_body(200, body, 'text/csv; charset=utf-8', extra_headers=[
                ('Content-Disposition', f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}")])
        if path == '/api/people':
            self.require_account(admin=True)
            return self.send_json(200, {'people': [accounts.public(r) for r in accounts.list_accounts()]})
        if path == '/api/admin':
            self.require_account(admin=True)
            return self.send_json(200, {
                'overview': costs.admin_overview(),
                'activity': [dict(row) for row in db.recent_activity(40)],
                'issues': [dict(row) for row in db.open_issue_reports()],
            })
        raise ApiError(404, 'Sayfa bulunamadı.')

    def route_post(self, path, query):
        data = self.read_json()
        if path == '/api/login':
            return self.login(data)
        if path == '/api/setup':
            return self.setup_admin(data)
        if path == '/api/register':
            account = accounts.create_registration(
                data.get('username'), data.get('first_name'), data.get('last_name'),
                data.get('email'), data.get('phone'), data.get('position'), data.get('password'))
            db.log_activity(account['id'], 'registration', 'Yönetici onayı bekliyor')
            return self.send_json(200, {'ok': True})
        if path == '/api/password-reset':
            account = accounts.request_password_reset(data.get('identifier'))
            if account:
                db.log_activity(account['id'], 'password_reset_request')
            return self.send_json(200, {'ok': True})
        if path == '/api/logout':
            account = self.require_account()
            db.log_activity(account['id'], 'logout')
            return self.send_json(200, {'ok': True}, cookies=[
                f'{accounts.COOKIE_NAME}=; {self.cookie_flags()}; Max-Age=0'])

        account = self.require_account()
        account_id = account['id']
        if path == '/api/calculate':
            result = costs.calculate_and_save(MARKET, account_id, data)
            total = result['summary']['total'] if result['summary'] else result['records'][0]['total']
            db.log_activity(account_id, 'calculation',
                            f'{len(result["records"])} görev · ₺{costs.format_tr(total)}')
            return self.send_json(200, result)
        if path == '/api/settings':
            before = costs.get_settings(account_id)
            settings = costs.save_settings(account_id, data.get('fuel_province'), data.get('solar_province'),
                                           data.get('monthly_salary'))
            if settings['fuel_province'] != before['fuel_province']:
                refresh_in_background([settings['fuel_province']])
            db.log_activity(account_id, 'settings',
                            f'{settings["fuel_province"]} / {settings["solar_province"]} / '
                            f'₺{costs.format_tr(settings["monthly_salary"])}')
            return self.send_json(200, {'settings': costs.settings_view(settings),
                                        'market': costs.market_view(MARKET, account_id)})
        if path == '/api/market/refresh':
            province = costs.get_settings(account_id)['fuel_province']
            result = MARKET.refresh([province])
            db.log_activity(account_id, 'market_refresh', province)
            return self.send_json(200, {'market': costs.market_view(MARKET, account_id),
                                        'eur_ok': result['eur_ok'], 'fuel_ok': result['fuel_ok']})
        match = re.fullmatch(r'/api/history/(\d+)/delete', path)
        if match:
            if not costs.delete_item(account_id, int(match.group(1))):
                raise ApiError(404, 'Kayıt bulunamadı.')
            db.log_activity(account_id, 'history_delete', f'Kayıt #{match.group(1)}')
            return self.send_json(200, {'ok': True})
        if path == '/api/history/clear':
            removed = costs.clear_history(account_id)
            db.log_activity(account_id, 'history_clear', f'{removed} kayıt')
            return self.send_json(200, {'ok': True, 'removed': removed})
        if path == '/api/password':
            updated = accounts.change_own_password(account, data.get('current'), data.get('new'))
            db.log_activity(account_id, 'password_change')
            return self.send_json(200, {'ok': True}, cookies=[self.session_cookie(updated, True)])
        if path == '/api/issues':
            message = str(data.get('message') or '').strip()
            if not 5 <= len(message) <= 2000:
                raise ApiError(400, 'Sorunu 5-2000 karakter arasında açıklayın.')
            report_id = db.create_issue_report(account_id, message)
            db.log_activity(account_id, 'issue_report', f'Bildirim #{report_id}')
            return self.send_json(200, {'ok': True})
        match = re.fullmatch(r'/api/admin/issues/(\d+)/resolve', path)
        if match:
            self.require_account(admin=True)
            if not db.resolve_issue_report(int(match.group(1)), account_id):
                raise ApiError(404, 'Bildirim bulunamadı veya zaten kapatılmış.')
            db.log_activity(account_id, 'issue_resolve', f'Bildirim #{match.group(1)}')
            return self.send_json(200, {'ok': True})
        if path == '/api/people':
            self.require_account(admin=True)
            created = accounts.create_account(data.get('username'), data.get('display_name'),
                                              data.get('password'), bool(data.get('is_admin')))
            role = 'yönetici' if created['is_admin'] else 'kullanıcı'
            db.log_activity(account_id, 'person_create', f'{created["display_name"]} (@{created["username"]}) · {role}')
            return self.send_json(200, {'person': accounts.public(created)})
        match = re.fullmatch(r'/api/people/(\d+)', path)
        if match:
            acting = self.require_account(admin=True)
            flag = lambda key: bool(data[key]) if key in data else None
            updated = accounts.update_account(int(match.group(1)), acting,
                                              display_name=data.get('display_name'),
                                              is_admin=flag('is_admin'), is_active=flag('is_active'),
                                              password=data.get('password') or None,
                                              approval_status=data.get('approval_status'))
            changes = []
            if 'display_name' in data:
                changes.append('adını değiştirdi')
            if 'is_admin' in data:
                changes.append('yönetici yaptı' if data['is_admin'] else 'yöneticiliğini kaldırdı')
            if 'is_active' in data:
                changes.append('etkinleştirdi' if data['is_active'] else 'pasif yaptı')
            if data.get('password'):
                changes.append('şifresini yeniledi')
            if data.get('approval_status') == 'approved':
                changes.append('üyeliğini onayladı')
            if data.get('approval_status') == 'rejected':
                changes.append('üyeliğini reddetti')
            detail = f'{updated["display_name"]} (@{updated["username"]}): ' + ', '.join(changes)
            db.log_activity(account_id, 'person_update', detail)
            return self.send_json(200, {'person': accounts.public(updated)})
        raise ApiError(404, 'Sayfa bulunamadı.')

    def login(self, data):
        username = str(data.get('username') or '').strip().lower()
        key = f'{self.client_ip()}|{username}'
        if throttle.is_blocked(key):
            raise ApiError(429, 'Çok fazla hatalı deneme yapıldı. Lütfen 15 dakika sonra tekrar deneyin.')
        account = accounts.authenticate(username, data.get('password'))
        if not account:
            throttle.record_failure(key)
            logger.warning('Başarısız giriş denemesi: kullanıcı=%s adres=%s', username[:40], self.client_ip())
            raise ApiError(401, 'Kullanıcı adı veya şifre hatalı.')
        throttle.clear(key)
        accounts.mark_login(account, ha_user=self.ha_user())
        db.log_activity(account['id'], 'login')
        self.send_json(200, {'ok': True}, cookies=[self.session_cookie(account, bool(data.get('remember')))])

    def setup_admin(self, data):
        key = f'{self.client_ip()}|kurulum'
        if not accounts.setup_required():
            raise ApiError(409, 'Kurulum zaten tamamlandı. Giriş yapın.')
        if throttle.is_blocked(key):
            raise ApiError(429, 'Çok fazla hatalı deneme yapıldı. Lütfen 15 dakika sonra tekrar deneyin.')
        if not accounts.check_setup_code(data.get('code')):
            throttle.record_failure(key)
            raise ApiError(400, 'Kurulum kodu hatalı. Kodu eklentinin Günlük sekmesinden kontrol edin.')
        account = accounts.create_account(data.get('username'), data.get('display_name'),
                                          data.get('password'), is_admin=True)
        accounts.clear_setup_code()
        throttle.clear(key)
        accounts.mark_login(account, ha_user=self.ha_user())
        db.log_activity(account['id'], 'setup')
        logger.info('İlk yönetici oluşturuldu: %s', account['username'])
        self.send_json(200, {'ok': True}, cookies=[self.session_cookie(account, True)])

    def send_static(self, name):
        path = (STATIC_DIR / name).resolve()
        if path.parent != STATIC_DIR.resolve() or path.suffix not in STATIC_TYPES or not path.is_file():
            raise ApiError(404, 'Sayfa bulunamadı.')
        cache = 'no-cache' if path.suffix == '.html' else 'public, max-age=300'
        self.send_body(200, path.read_bytes(), STATIC_TYPES[path.suffix], cache=cache)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Tarayıcının boşta bıraktığı bağlantıyı kapatması hata değildir; günlüğü kirletmesin.
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError)):
            return
        logger.exception('Bağlantı işlenemedi: %s', client_address[0])


class IngressHandler(Handler):
    ingress = True


class PublicHandler(Handler):
    ingress = False


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    db.init_db()
    accounts.announce_setup_code()
    if os.environ.get('MARKET_REFRESH', '1') != '0':
        threading.Thread(target=market_loop, name='market-loop', daemon=True).start()
    ingress_port = int(os.environ.get('INGRESS_PORT', '8099'))
    web_port = int(os.environ.get('WEB_PORT', '8102'))
    ingress = Server(('0.0.0.0', ingress_port), IngressHandler)
    public = Server(('0.0.0.0', web_port), PublicHandler)
    threading.Thread(target=ingress.serve_forever, name='ingress', daemon=True).start()
    logger.info('Web sitesi hazır: port %s (site), %s (Home Assistant paneli). Veri klasörü: %s',
                web_port, ingress_port, db.DATA_DIR.resolve())
    public.serve_forever()


if __name__ == '__main__':
    main()
