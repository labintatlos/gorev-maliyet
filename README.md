# Görev Maliyet Hesaplayıcı

**Web Sitesi** | **Home Assistant Eklentisi**

Avara ve aborda saatleri, harcanan yakıt ve personel sayısıyla görev süresini ve görev maliyetini (amortisman + personel + yakıt) Excel formülüyle birebir hesaplayan, GÖRRAP satırını hazırlayan web sitesi. Telefondan ve bilgisayardan kullanıcı adı ve şifreyle açılır; Telegram'a bağımlılığı yoktur. Home Assistant OS yalnızca sunucuyu çalıştıran makinedir.

## ⚓ Özellikler

### 🧮 Hesapla
Görev tarihi, yakıt türü (dizel/benzin) ve personel ortaktır; her görev için avara, aborda ve yakıt litresi girilir. Aynı gün birden fazla görev tek seferde hesaplanır.

- **Canlı maliyet önizlemesi:** Değerler değiştikçe toplam maliyet, amortisman/personel/yakıt payları, saatlik ortalama ve gündüz/gece süresi anında görünür.
- **24 saatlik zaman çizelgesi:** Her görevin gece ve gündüz saatlerine denk gelen kısmı görünür; gece yarısını geçen görevler desteklenir.
- **Hızlı doldurma:** Son hesaplama, son 4 saat ve örnek değerler.
- **Sonuç raporu:** Toplam, dağılım çubuğu, yakıt ağırlığı ve verimi, kullanılan Euro/litre fiyatı/maaş ve tek dokunuşla kopyalanan GÖRRAP satırı. Birden fazla görevde günlük toplam ve bütün GÖRRAP satırları.
- **Çevrimdışı bekletme:** Bağlantı yokken kaydedilen hesaplama cihazda bekletilir, bağlantı gelince gönderilir.

### 📚 Geçmiş ve 📊 İstatistik
Kişiye özel hesap geçmişi, kayıt detayı, "bu değerlerle hesapla", kayıt silme ve Excel'de doğrudan açılan **CSV** çıktısı. İstatistik sayfasında bu ay, son 7 gün, geçen ay ve tüm zamanlar; geçen aya göre değişim ve maliyet dağılımı.

### ⚙️ Ayarlar
- **Sabit ayarlar:** Akaryakıt fiyat ili, gün doğumu/batımı ili (81 il) ve aylık personel maaşı kişi başına bir kez seçilir.
- **Otomatik veriler:** Euro kuru TCMB döviz satıştan, benzin ve motorin fiyatı seçili ilin Petrol Ofisi sayfasından otomatik alınır; site açılışında ve her gün 17:00'de yenilenir, istenirse elle yenilenir.
- **Excel sabitleri:** Günlük amortisman €70, dizel 0,82 kg/L, benzin 0,745 kg/L, saatlik maaş = aylık maaş / 720.

### 👤 Üyelik, Kişiler ve Yönetim
Su Ürünleri ve Aile Bütçe siteleriyle aynı giriş sistemi: kurulum koduyla ilk yönetici, yönetici onaylı **Üye ol**, **Şifremi unuttum** talebi, **Kişiler / Şifreler** ekranı, **Sorun bildir**. Yönetim sayfasında bugünkü ve toplam hesaplama, son 7 gün grafiği, kişi başına kullanım, açık sorun bildirimleri ve son işlemler görünür; parolalar kayda alınmaz.

### 🌗 Aydınlık / Karanlık Görünüm
Site cihazın görünüm ayarını izler; üst çubuktaki düğmeyle değiştirilebilir. Telefonda sayfalar alttaki gezinme çubuğundan açılır.

## 🚀 Kurulum

Depoyu Home Assistant'a eklenti deposu olarak ekleyin ve **Görev Maliyet Hesaplayıcı** eklentisini kurun:

**Ayarlar → Eklentiler → Eklenti Mağazası → ⋮ → Depolar →** `https://github.com/labintatlos/gorev-maliyet`

İlk açılışta site bir **kurulum kodu** ister; kod eklentinin **Günlük** sekmesinde yazar. Ev dışından HTTPS ile açmak için KeenDNS adımları [DEPLOYMENT.md](DEPLOYMENT.md) içindedir.

| Adres | Giriş |
|-------|-------|
| Home Assistant yan menüsündeki **Görev Maliyet** | HA oturumu (ilk seferde bir kez site şifresi) |
| `http://homeassistant.local:8102` (ev ağı) | kullanıcı adı ve şifre |
| KeenDNS adresi (HTTPS) | kullanıcı adı ve şifre |

### Yerel Çalıştırma

Hiçbir paket kurmak gerekmez (yalnızca Python 3.11+ standart kütüphanesi):

```bash
cd gorev_maliyet
python web.py                    # http://localhost:8102
```

Doğrulama betikleri:

```bash
python tools/smoke_test.py       # uçtan uca API testi (internet gerekmez)
python tools/check_market.py     # TCMB ve Petrol Ofisi'nden gerçek veri
python tools/browser_check.py    # gerçek tarayıcıda gezinme ve ekran görüntüsü
```

## 🏗️ Yapı

```
gorev_maliyet/
├── web.py            # HTTP sunucusu: giriş, oturum, API, statik dosyalar, piyasa verisi zamanlayıcısı
├── costs.py          # Sabit ayarlar, hesaplama, geçmiş, istatistik, CSV, yönetim özeti
├── calculator.py     # Excel formülleri (süre, amortisman, personel, yakıt, GÖRRAP)
├── solar_time.py     # İl koordinatına göre gün doğumu/batımı ve gece-gündüz ayrımı
├── market_data.py    # TCMB Euro kuru ve Petrol Ofisi il fiyatları (önbellekli)
├── provinces.py      # 81 il ve koordinatları
├── accounts.py       # Kişiler, şifre özeti, oturum çerezi, kurulum kodu, giriş kilidi
├── db.py             # SQLite şeması ve işlem kayıtları
├── static/           # Arayüz (index.html, app.js, calc.js, style.css, theme.js)
├── config.yaml       # Home Assistant eklenti tanımı
├── Dockerfile
└── run.sh            # Eklenti giriş noktası
tools/                # Duman testi, canlı veri ve tarayıcı kontrolleri
```

## 📊 Veritabanı

Veritabanı Home Assistant'ta `/share/gorev_maliyet/gorev_maliyet.db` içindedir; eklenti güncellense veya yeniden kurulsa da silinmez.

`web_accounts` (kişiler ve üyelik onayı), `password_reset_requests`, `user_settings` (kişinin il ve maaş ayarları), `calculations` (her görevin girdileri, kullanılan Euro/fiyat/maaş ve maliyet sonuçları), `activity_log` (işlem kayıtları), `issue_reports` (sorun bildirimleri).

## ⚠️ Sorumluluk

Site bir hesap yardımcısıdır. Kullanılan Euro kuru ve akaryakıt fiyatı otomatik kaynaklardan alınır; resmi evrakta kullanmadan önce değerleri kontrol edin.
