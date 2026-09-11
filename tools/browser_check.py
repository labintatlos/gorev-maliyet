"""Tarayıcı kontrolü: siteyi gerçek Chrome'da açar, giriş yapar, sayfaları dolaşır ve ekran görüntüsü alır.

    python tools/browser_check.py [çıktı_klasörü]

Gerekli: Google Chrome veya Microsoft Edge ve `pip install websockets`
(yalnızca bu geliştirme betiği için; eklentinin kendisi standart kütüphaneyle çalışır).

Duman testi gibi geçici veritabanı ve sabit piyasa verisiyle çalışır. Formdan
giriş yapar, görev ekleyip hesaplar, geçmiş/istatistik/ayarlar/yönetim
sayfalarını telefon (390 px) ve masaüstü (1280 px) genişliğinde çeker, karanlık
görünümü dener. Konsol hatası, CSP ihlali veya beklenen öğe yoksa 1 ile çıkar.
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))

import smoke_test as smoke  # noqa: E402  (sabit piyasa verisi, istemci ve portlar ortak)

try:
    import websockets
except ImportError:
    sys.exit('Bu betik için websockets paketi gerekir: pip install websockets')

CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
]
DEBUG_PORT = 9333
BASE = smoke.BASE


def start_server(work):
    (work / 'market_data.json').write_text(json.dumps(smoke.MARKET), encoding='utf-8')
    env = dict(os.environ, WEB_PORT=str(smoke.WEB_PORT), INGRESS_PORT=str(smoke.INGRESS_PORT),
               GOREV_MALIYET_DATA=str(work), MARKET_REFRESH='0', TZ='Europe/Istanbul',
               PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    log = open(work / 'server.log', 'w', encoding='utf-8')
    proc = subprocess.Popen([sys.executable, '-u', str(smoke.ADDON / 'web.py')], cwd=str(smoke.ADDON), env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    client = smoke.Client()
    for _ in range(100):
        try:
            if client.call('/health')[0] == 200:
                break
        except OSError:
            time.sleep(0.2)
    return proc, log


def seed(work):
    """Sayfaların dolu görünmesi için örnek kişiler, hesaplamalar ve bildirimler oluşturur."""
    duty = smoke.duty
    today = smoke.TODAY.isoformat()
    admin = smoke.Client()
    code = (work / 'setup_code').read_text(encoding='ascii')
    admin.call('/api/setup', {'code': code, 'username': 'deneme', 'display_name': 'Deneme Yönetici',
                              'password': 'DenemeSifre123!'})
    admin.call('/api/calculate', {'duty_date': today, 'personnel': 3, 'fuel_type': 'diesel',
                                  'duties': [duty('22:00', '01:30', 10.5), duty('06:00', '08:15', 120)]})
    admin.call('/api/calculate', {'duty_date': today, 'personnel': 4, 'fuel_type': 'diesel',
                                  'duties': [duty('09:35', '19:25', 750)]})
    previous = (smoke.TODAY.replace(day=1) - smoke.timedelta(days=3)).isoformat()
    admin.call('/api/calculate', {'duty_date': previous, 'personnel': 2, 'fuel_type': 'gasoline',
                                  'duties': [duty('10:00', '14:00', 200)]})
    admin.call('/api/people', {'username': 'saha', 'display_name': 'Saha Personeli', 'password': 'SahaSifre123!'})
    field = smoke.Client()
    field.call('/api/login', {'username': 'saha', 'password': 'SahaSifre123!'})
    field.call('/api/calculate', {'duty_date': today, 'personnel': 5, 'fuel_type': 'diesel',
                                  'duties': [duty('13:00', '17:30', 320)]})
    field.call('/api/issues', {'message': 'Görev tarihi alanı telefonda küçük görünüyor.'})
    smoke.Client().call('/api/register', {'first_name': 'Aday', 'last_name': 'Kişi', 'email': 'aday@example.com',
                                          'phone': '0532 123 45 67', 'position': 'uzman', 'username': 'aday',
                                          'password': 'AdaySifre123!'})


class Page:
    def __init__(self, ws):
        self.ws = ws
        self.counter = 0
        self.pending = {}
        self.events = []

    async def start(self):
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        async for raw in self.ws:
            message = json.loads(raw)
            if 'id' in message and message['id'] in self.pending:
                self.pending.pop(message['id']).set_result(message)
            elif 'method' in message:
                self.events.append(message)

    async def send(self, method, **params):
        self.counter += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.counter] = future
        await self.ws.send(json.dumps({'id': self.counter, 'method': method, 'params': params}))
        message = await asyncio.wait_for(future, 30)
        if 'error' in message:
            raise RuntimeError(f'{method}: {message["error"]}')
        return message.get('result', {})

    async def js(self, expression):
        result = await self.send('Runtime.evaluate', expression=expression, awaitPromise=True, returnByValue=True)
        if 'exceptionDetails' in result:
            details = result['exceptionDetails']
            raise RuntimeError(f'JS hatası: {details.get("exception", {}).get("description") or details}')
        return result.get('result', {}).get('value')

    async def wait_for(self, expression, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.js(expression):
                return
            await asyncio.sleep(0.15)
        raise AssertionError(f'Beklenen durum oluşmadı: {expression}')

    async def goto(self, url):
        await self.send('Page.navigate', url=url)
        await asyncio.sleep(0.4)
        await self.wait_for("document.readyState === 'complete'")

    async def viewport(self, width, height, mobile):
        await self.send('Emulation.setDeviceMetricsOverride', width=width, height=height,
                        deviceScaleFactor=1, mobile=mobile)
        await asyncio.sleep(0.2)

    async def media(self, dark):
        await self.send('Emulation.setEmulatedMedia', features=[
            {'name': 'prefers-color-scheme', 'value': 'dark' if dark else 'light'},
            {'name': 'prefers-reduced-motion', 'value': 'reduce'},
        ])

    async def shot(self, path, max_height=3600):
        await asyncio.sleep(0.35)
        size = (await self.send('Page.getLayoutMetrics'))['cssContentSize']
        clip = {'x': 0, 'y': 0, 'width': size['width'], 'height': min(size['height'], max_height), 'scale': 1}
        data = await self.send('Page.captureScreenshot', format='png', clip=clip, captureBeyondViewport=True)
        path.write_bytes(base64.b64decode(data['data']))
        print('  görüntü', path.name)


async def browse(out, failures):
    targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{DEBUG_PORT}/json/list'))
    target = next(t for t in targets if t['type'] == 'page')
    async with websockets.connect(target['webSocketDebuggerUrl'], max_size=None) as ws:
        page = Page(ws)
        await page.start()
        for domain in ('Page', 'Runtime', 'Log'):
            await page.send(f'{domain}.enable')

        async def step(name, coroutine):
            try:
                await coroutine
                print(f'  ok    {name}')
            except Exception as exc:
                failures.append(f'{name}: {exc}')
                print(f'  FAIL  {name}: {exc}')

        await page.media(dark=False)
        await page.viewport(1280, 900, False)
        await page.goto(BASE + '/')
        await step('giriş ekranı', page.wait_for("!document.querySelector('#login-form').hidden"))
        await page.shot(out / '01-giris-1280.png')
        await page.viewport(390, 844, True)
        await page.shot(out / '02-giris-390.png')

        await page.js("""(() => { const f = document.querySelector('#login-form');
            f.username.value = 'deneme'; f.password.value = 'DenemeSifre123!'; f.requestSubmit(); return true; })()""")
        await step('formdan giriş ve hesaplama sayfası', page.wait_for(
            "!document.querySelector('#app').hidden && document.querySelectorAll('.duty').length === 1"))
        await step('canlı maliyet önizlemesi', page.wait_for(
            "document.querySelector('#sum-total').textContent.includes('₺')"))
        await page.shot(out / '03-hesapla-390.png')

        before = await page.js("document.querySelector('#sum-total').textContent")
        await page.js("document.querySelector('#btn-add-duty').click(); true")
        await step('görev ekle', page.wait_for("document.querySelectorAll('.duty').length === 2"))
        await page.js("""document.querySelector('.duty [data-action="nudge"][data-delta="60"]').click(); true""")
        after = await page.js("document.querySelector('#sum-total').textContent")
        await step('saat düğmesi toplamı değiştirir', page.wait_for(f"document.querySelector('#sum-total').textContent !== {json.dumps(before)}"))
        print('    önizleme:', before, '→', after)
        await page.viewport(1280, 900, False)
        await page.shot(out / '04-hesapla-1280.png')

        await page.js("document.querySelector('#btn-submit').click(); true")
        await step('hesapla ve kaydet', page.wait_for(
            "!document.querySelector('#result-view').hidden && document.querySelectorAll('#result-list .report').length === 2", 20))
        await step('günlük toplam kartı', page.wait_for("document.querySelector('#result-summary .summary-report') !== null"))
        await page.shot(out / '05-sonuc-1280.png')
        await page.viewport(390, 844, True)
        await page.shot(out / '06-sonuc-390.png')

        await page.js("location.hash = '#gecmis'; true")
        await step('geçmiş listesi', page.wait_for("document.querySelectorAll('.history-item').length >= 6"))
        await page.shot(out / '07-gecmis-390.png')
        await page.js("document.querySelector('.history-item').click(); true")
        await step('kayıt penceresi', page.wait_for("document.querySelector('#record-dialog').open"))
        await page.shot(out / '08-kayit-390.png')
        await page.js("document.querySelector('#record-reuse').click(); true")
        await step('kayıttaki değerlerle hesapla', page.wait_for(
            "location.hash === '#hesapla' && !document.querySelector('#calc-view').hidden"))

        await page.js("location.hash = '#istatistik'; true")
        await step('istatistik', page.wait_for("document.querySelectorAll('#stats-periods .card').length === 4"))
        await page.shot(out / '09-istatistik-390.png')

        await page.viewport(1280, 900, False)
        await page.js("location.hash = '#ayarlar'; true")
        await step('ayarlar', page.wait_for("document.querySelectorAll('#set-fuel option').length === 81"))
        await page.shot(out / '10-ayarlar-1280.png')

        await page.js("location.hash = '#yonetim'; true")
        await step('yönetim', page.wait_for(
            "document.querySelectorAll('#admin-tiles .tile').length === 5 && document.querySelectorAll('#admin-activity li').length > 3"))
        await page.shot(out / '11-yonetim-1280.png')
        await page.js("document.querySelector('#admin-people').click(); true")
        await step('kişiler penceresi', page.wait_for(
            "document.querySelector('#people-dialog').open && document.querySelectorAll('#people-list .person').length === 3"))
        await page.shot(out / '12-kisiler-1280.png')
        await page.js("document.querySelector('#people-dialog').close(); true")

        await page.media(dark=True)
        await page.viewport(390, 844, True)
        await page.goto(BASE + '/#hesapla')
        await step('karanlık görünüm', page.wait_for(
            "document.documentElement.dataset.theme === 'dark' && document.querySelectorAll('.duty').length > 0"))
        await page.shot(out / '13-hesapla-karanlik-390.png')

        await asyncio.sleep(0.5)
        problems = []
        for event in page.events:
            method, params = event['method'], event['params']
            if method == 'Runtime.exceptionThrown':
                problems.append(params['exceptionDetails'].get('exception', {}).get('description') or str(params))
            elif method == 'Runtime.consoleAPICalled' and params['type'] in ('error', 'assert'):
                problems.append(' '.join(str(a.get('value') or a.get('description')) for a in params['args']))
            elif method == 'Log.entryAdded' and params['entry']['level'] == 'error':
                problems.append(params['entry']['text'])
        for problem in problems:
            failures.append(f'konsol: {problem}')
            print(f'  FAIL  konsol: {problem[:300]}')
        if not problems:
            print('  ok    konsolda hata veya CSP ihlali yok')


def main():
    chrome = next((c for c in CHROME_CANDIDATES if Path(c).exists()), None)
    if not chrome:
        sys.exit('Chrome veya Edge bulunamadı.')
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix='gorevmaliyet_ekran_'))
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='gorevmaliyet_tarayici_'))
    server, log = start_server(work)
    browser = None
    failures = []
    try:
        seed(work)
        browser = subprocess.Popen([chrome, '--headless=new', f'--remote-debugging-port={DEBUG_PORT}',
                                    f'--user-data-dir={work / "profil"}', '--no-first-run',
                                    '--no-default-browser-check', '--disable-gpu', 'about:blank'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{DEBUG_PORT}/json/version', timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        asyncio.run(browse(out, failures))
    finally:
        if browser:
            browser.terminate()
            browser.wait()
        server.terminate()
        server.wait()
        log.close()
    server_log = (work / 'server.log').read_text(encoding='utf-8')
    if 'Traceback' in server_log:
        failures.append('sunucu günlüğünde hata var')
        print(server_log[-3000:])
    print('ekran görüntüleri:', out)
    print('errors:', len(failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
