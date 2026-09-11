"""Canlı kaynak kontrolü: TCMB Euro kuru ve Petrol Ofisi il fiyatlarını gerçekten çeker.

    python tools/check_market.py                 # Samsun, İstanbul, Afyonkarahisar, Ankara
    python tools/check_market.py İzmir Mersin    # istenen iller

İnternet gerekir. Kaynak sitelerin sayfa yapısı değiştiğinde ayrıştırıcının hâlâ
çalıştığını doğrulamak için kullanılır; hata varsa 1 ile çıkar.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'gorev_maliyet'))
sys.stdout.reconfigure(encoding='utf-8')

from market_data import fetch_petrol_ofisi_prices, fetch_tcmb_eur_selling  # noqa: E402

failures = 0
try:
    eur, source_date = fetch_tcmb_eur_selling()
    print(f'TCMB EUR döviz satış: {eur} ({source_date})')
except Exception as exc:
    failures += 1
    print(f'TCMB HATA: {exc}')

for province in sys.argv[1:] or ['Samsun', 'İstanbul', 'Afyonkarahisar', 'Ankara']:
    try:
        gasoline, diesel = fetch_petrol_ofisi_prices(province)
        print(f'{province}: benzin {gasoline} TL/L, motorin {diesel} TL/L')
    except Exception as exc:
        failures += 1
        print(f'{province} HATA: {exc}')

sys.exit(1 if failures else 0)
