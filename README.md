# Görev Maliyet Telegram Botu — v3.7.0

Home Assistant OS için yerel App/Add-on ve bağımsız Telegram botu.

## 🆕 v3.7 ile gelenler

- **💰 Canlı maliyet önizlemesi:** Hesap paneli ve Mini App, değerleri değiştirdikçe tahmini toplam maliyeti gösterir.
- **📊 İstatistikler:** Bu ay, son 7 gün, geçen ay ve tüm zamanlar için görev sayısı, süre, yakıt ve maliyet özeti.
- **📤 CSV dışa aktarma:** Tüm geçmiş, Excel'de doğrudan açılabilen dosya olarak indirilir.
- **🧾 Günlük toplam:** Mini App'ten birden fazla görev gönderildiğinde toplam süre, yakıt, maliyet ve tüm GÖRRAP satırları tek mesajda.
- **📱 Yenilenen Mini App:** Gündüz/gece zaman çizelgesi, maliyet dağılım çubuğu, çalışan çevrimdışı kayıt kuyruğu.

Ayrıntılar için [CHANGELOG.md](CHANGELOG.md).

## 📱 Telegram Mini App (Web App)

- **Tek ekranda birden fazla görev:** Avara, Aborda, yakıt litresi görev başına; tarih, yakıt türü ve personel ortak.
- **Canlı önizleme:** Bot, klavyedeki `📱 Mini App Aç` butonunun adresine güncel Euro kuru, seçili ilin motorin/benzin fiyatı, aylık maaş ve gün doğumu/batımı saatlerini ekler. Mini App bu verilerle toplam maliyeti, amortisman/personel/yakıt paylarını ve gündüz/gece süresini anında gösterir. **Kesin hesap her zaman bot tarafında güncel verilerle yapılır.**
- **Çevrimdışı kayıt:** Bağlantı yokken gönderilen görevler cihazda saklanır; bağlantı gelince `📤 Bota gönder` ile tek seferde iletilir.
- **Tema ve dokunsal geri bildirim:** Telegram'ın açık/koyu temasına uyar.

> ⚠️ Telegram, Mini App'in bota veri gönderebilmesini (`sendData`) yalnızca **klavye butonundan** açılışta destekler. Bu yüzden sohbet menü butonu komut listesini açar. Mini App için `/start` yazıp klavyedeki `📱 Mini App Aç` butonunu kullanın. Sabit ayarları değiştirdikten sonra önizlemenin güncellenmesi için yeniden `/start` yazın.

### Mini App Barındırma (Hosting)
Mini App tamamen `webapp/` klasöründeki statik dosyalardan (HTML/CSS/JS) oluşur:
1. **GitHub Pages (Tavsiye Edilen):** `webapp/` klasörünü ücretsiz bir GitHub repository'sine yükleyip Pages'i etkinleştirin (örn: `https://kullanici.github.io/gorev-webapp/`).
2. **Kendi Sunucunuz:** Home Assistant Nabu Casa, Cloudflare Tunnel veya HTTPS reverse proxy altındaki web dizinine koyun.
3. Bot yapılandırmasında `webapp_url` alanına bu HTTPS linkini girin.

## 🤖 Komutlar

| Komut | Açıklama |
| --- | --- |
| `/start`, `/menu` | Ana menü ve hızlı klavye (Mini App butonu dahil) |
| `/hesapla` | Bot içinde yeni görev hesaplaması |
| `/gecmis` | Geçmiş hesaplamalar |
| `/istatistik` | Aylık özet ve istatistikler |
| `/disaaktar` | Geçmişi CSV (Excel) olarak indir |
| `/ayarlar` | Sabit ayarlar: akaryakıt ili, güneş ili, maaş |
| `/veriler` | Euro ve akaryakıt verileri, elle yenileme |
| `/webapp`, `/miniapp` | Mini App klavye butonunu göster |
| `/sabitler` | Excel sabitleri |
| `/iptal` | Bekleyen girişi iptal et |
| `/id` | Telegram kullanıcı ID'si |
| `/yonetici` | Yönetici paneli (yalnızca yönetici) |

## ⚙️ Sabit Ayarlar

Telegram ana menüsündeki **⚙️ Sabit Ayarlar** bölümünde kullanıcı bir kez şunları seçer:

- **Akaryakıt fiyat ili:** Petrol Ofisi benzin/motorin fiyatlarının alınacağı il (81 il destekli).
- **Gün doğumu/batımı ili:** Gece ve gündüz görev süresinin hesaplanacağı il.
- **Aylık personel maaşı:** Personel maliyetinde kullanılacak aylık maaş.

Bu seçimler kullanıcı bazında SQLite veritabanında saklanır ve sonraki hesaplamalarda otomatik kullanılır.

Euro kuru TCMB'den, benzin ve motorin fiyatları seçili ilin Petrol Ofisi fiyat sayfasından otomatik alınır. Piyasa verileri bot açılışında ve her gün 17:00'de yenilenir.

## Güncelleme

Mevcut App'i kaldırmayın. Yeni klasör içeriğini mevcut `addons/gorev_maliyet_haos_addon` klasörünün üzerine yazın, App Store'da **Check for updates / Güncellemeleri kontrol et** deyip 3.7.0 sürümüne güncelleyin. Mini App'i ayrıca barındırıyorsanız `webapp/` klasörünü de güncelleyin. Veritabanı ve geçmiş kayıtları korunur.

## 👑 Yönetici Paneli

Ana menüdeki **👑 Yönetici Paneli** yalnızca yönetici hesabında görünür. Panel, bot kullanımına ilişkin işlem özetlerini ve kullanım istatistiklerini yalnızca yetkili yöneticiye sunar.

`admin_user_ids` boş bırakılırsa `authorized_user_ids` alanındaki **ilk ID** otomatik olarak yönetici kabul edilir. İstersen `admin_user_ids` alanına yalnızca kendi Telegram ID'ni yazarak yöneticiyi açıkça belirleyebilirsin.

### Kullanıcı İsimlendirme

Yönetici, **👑 Yönetici Paneli → 👥 Kullanıcılar** üzerinden yetkili kullanıcılara kendi belirlediği görünen isimleri verebilir. Bu isimler yönetici ekranlarında kullanılır ve yeniden başlatmalarda korunur.
