# Görev Maliyet Telegram Botu — v3.6.0

Home Assistant OS için yerel App/Add-on ve bağımsız Telegram botu.

## 📱 v3.6 ile gelen Telegram Mini App (Web App)

Kullanıcılar artık butonlarla tek tek uğraşmak yerine Telegram içinde açılan modern **Mini App** formu üzerinden saniyeler içinde görev hesaplayabilir:

- **Hızlı Giriş:** Avara, Aborda, Tarih, Personel ve Yakıt miktarı tek ekranda girilir.
- **Canlı Önizleme:** Seçilen saatlere göre toplam görev süresi ve yaklaşık yakıt ağırlığı (kg) anında hesaplanır.
- **Haptic & Tema:** Telegram'ın açık/koyu temasına otomatik uyum sağlar, dokunsal geri bildirim verir.
- **Kolay Erişim:** Telegram sohbetinin sol altındaki `📱 Hesapla` menü butonundan veya ana menüden tek dokunuşla açılır.

### Mini App Barındırma (Hosting)
Mini App tamamen `webapp/` klasöründeki statik dosyalardan (HTML/CSS/JS) oluşur:
1. **GitHub Pages (Tavsiye Edilen):** `webapp/` klasörünü ücretsiz bir GitHub repository'sine yükleyip Pages'i etkinleştirin (örn: `https://kullanici.github.io/gorev-webapp/`).
2. **Kendi Sunucunuz:** Home Assistant Nabu Casa, Cloudflare Tunnel veya HTTPS reverse proxy altındaki web dizinine koyun.
3. Bot yapılandırmasında `webapp_url` alanına bu HTTPS linkini girin.

## ⚙️ Sabit Ayarlar

Telegram ana menüsündeki **⚙️ Sabit Ayarlar** bölümünde kullanıcı bir kez şunları seçer:

- **Akaryakıt fiyat ili:** Petrol Ofisi benzin/motorin fiyatlarının alınacağı il (81 il destekli).
- **Gün doğumu/batımı ili:** Gece ve gündüz görev süresinin hesaplanacağı il.
- **Aylık personel maaşı:** Personel maliyetinde kullanılacak aylık maaş.

Bu seçimler kullanıcı bazında SQLite veritabanında saklanır ve sonraki hesaplamalarda otomatik kullanılır.

Euro kuru TCMB'den, benzin ve motorin fiyatları seçili ilin Petrol Ofisi fiyat sayfasından otomatik alınır. Piyasa verileri bot açılışında ve her gün 17:00'de yenilenir.

## Sürüm Notu — 3.6.0

Bu sürüm **Telegram Mini App (Web App) entegrasyonu, hızlı form hesaplama ve genel kararlılık geliştirmeleri** içerir.

## Güncelleme

Mevcut App'i kaldırmayın. Yeni klasör içeriğini mevcut `addons/gorev_maliyet_haos_addon` klasörünün üzerine yazın, App Store'da **Check for updates / Güncellemeleri kontrol et** deyip 3.6.0 sürümüne güncelleyin.

## 👑 Yönetici Paneli

Ana menüdeki **👑 Yönetici Paneli** yalnızca yönetici hesabında görünür. Panel, bot kullanımına ilişkin işlem özetlerini ve kullanım istatistiklerini yalnızca yetkili yöneticiye sunar.

`admin_user_ids` boş bırakılırsa `authorized_user_ids` alanındaki **ilk ID** otomatik olarak yönetici kabul edilir. İstersen `admin_user_ids` alanına yalnızca kendi Telegram ID'ni yazarak yöneticiyi açıkça belirleyebilirsin.

### Kullanıcı İsimlendirme

Yönetici, **👑 Yönetici Paneli → 👥 Kullanıcılar** üzerinden yetkili kullanıcılara kendi belirlediği görünen isimleri verebilir. Bu isimler yönetici ekranlarında kullanılır ve yeniden başlatmalarda korunur.
