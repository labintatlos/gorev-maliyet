"""WebKit ile form sınırları ve tarih/saat giriş kontrolü.

Geliştirme bağımlılığı: pip install playwright; python -m playwright install webkit
Çalıştırma: python tools/webkit_check.py [çıktı_klasörü]
Windows WebKit kontrolü gerçek iPhone/Safari doğrulamasının yerini tutmaz.
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

import browser_check as browser


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix='gorev_webkit_'))
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='gorev_webkit_data_'))
    server, log = browser.start_server(work)
    errors = []
    try:
        browser.seed(work)
        with sync_playwright() as p:
            engine = p.webkit.launch()
            for theme in ('light', 'dark'):
                context = engine.new_context(viewport={'width': 390, 'height': 844},
                                             is_mobile=True, has_touch=True, locale='tr-TR',
                                             color_scheme=theme, reduced_motion='reduce')
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(browser.BASE)
                page.locator('#login-form input[name=username]').fill('deneme')
                page.locator('#login-form input[name=password]').fill('DenemeSifre123!')
                page.locator('#login-form button[type=submit]').click()
                page.locator('.duty').wait_for()
                for width in (320, 368, 390, 768, 1280):
                    page.set_viewport_size({'width': width, 'height': 844})
                    page.evaluate('window.scrollTo(0, 0)')
                    page.wait_for_timeout(100)
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                    overflow = page.evaluate(browser.CONTROL_OVERFLOWS)
                    assert not overflow, f'{theme} {width}: {overflow}'
                    page.screenshot(path=str(out / f'{theme}-{width}.png'), full_page=True)
                    print(f'  ok    {theme} {width}: alanlar kart sınırları içinde')
                page.set_viewport_size({'width': 390, 'height': 844})
                page.locator('#duty-date').fill(browser.smoke.TODAY.isoformat())
                before = page.locator('#sum-total').inner_text()
                page.locator('.duty input[type=time]').first.fill('10:35')
                page.locator('.duty input[type=time]').first.press('Tab')
                page.wait_for_function('(before) => document.querySelector("#sum-total").textContent !== before', arg=before)
                page.locator('label[for=fuel-gasoline]').click()
                page.wait_for_function('document.querySelector("#fuel-gasoline").checked && document.querySelector("#mk-fuel-label").textContent === "Benzin"')
                page.locator('#btn-submit').click()
                page.locator('#result-view').wait_for(state='visible')
                print(f'  ok    {theme}: tarih/saat girişi, yakıt seçimi ve kayıt')
                context.close()
            engine.close()
        assert not errors, errors
        print('errors: 0')
    finally:
        server.terminate()
        server.wait()
        log.close()


if __name__ == '__main__':
    main()
