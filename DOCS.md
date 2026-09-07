# Görev Maliyet Telegram Botu — v3.6.0

Home Assistant OS için yerel App/Add-on.

## 📱 v3.6 Telegram Mini App (Web App)

Telegram içinde tam ekran açılan yeni **Mini App** özelliği ile görev hesaplama adımları tek bir ekrana indirgenmiştir:

- **Hızlı Giriş Formu:** Avara, Aborda, Görev Tarihi, Personel ve Yakıt litresi.
- **Dinamik Süre Hesabı:** Saatler değiştikçe toplam görev süresini ve tahmini yakıt ağırlığını anlık gösterir.
- **Yerel Telegram Entegrasyonu:** Telegram WebApp SDK ile `sendData` üzerinden tek tuşla bota geri bildirim yapar.
- **Kullanım:** Telegram sol alt köşedeki menü butonundan (`📱 Hesapla`) veya bot içindeki `📱 Mini App ile Hesapla` butonundan başlatılabilir.

### Mini App Yapılandırması
`config.yaml` / Add-on seçeneklerinde `webapp_url` alanına GitHub Pages veya kendi HTTPS web sunucunuzdaki URL girildiğinde tüm kullanıcılarda Mini App aktif olur.

## ⚙️ Sabit Ayarlar

Telegram ana menüsündeki **⚙️ Sabit Ayarlar** bölümünde kullanıcı bir kez şunları seçer:

- **Akaryakıt fiyat ili:** Petrol Ofisi benzin/motorin fiyatlarının alınacağı il (81 il).
- **Gün doğumu/batımı ili:** Gece ve gündüz görev süresinin hesaplanacağı il.
- **Aylık personel maaşı:** Personel maliyetinde kullanılacak aylık maaş.

Bu seçimler kullanıcı bazında SQLite veritabanında saklanır ve sonraki hesaplamalarda otomatik kullanılır.

Euro kuru TCMB'den, benzin ve motorin fiyatları seçili ilin Petrol Ofisi fiyat sayfasından otomatik alınır. Piyasa verileri bot açılışında ve her gün 17:00'de yenilenir.

## Sürüm Notu — 3.6.0

Bu sürüm **Telegram Mini App (Web App) entegrasyonu, hızlı form hesaplama ve genel yönetim ekranı iyileştirmeleri** içerir.

## Güncelleme

Mevcut App'i kaldırmayın. Yeni klasör içeriğini mevcut `addons/gorev_maliyet_haos_addon` klasörünün üzerine yazın, App Store'da **Check for updates / Güncellemeleri kontrol et** deyip 3.6.0 sürümüne güncelleyin.

## 👑 Yönetici Paneli

Ana menüdeki **👑 Yönetici Paneli** yalnızca yönetici hesabında görünür. Panel, bot kullanımına ilişkin işlem özetlerini ve kullanım istatistiklerini yalnızca yetkili yöneticiye sunar.

`admin_user_ids` boş bırakılırsa `authorized_user_ids` alanındaki **ilk ID** otomatik olarak yönetici kabul edilir.

### Kullanıcı İsimleri

**👑 Yönetici Paneli → 👥 Kullanıcılar** bölümünden yetkili kullanıcılara yönetici tarafından özel görünen ad verilebilir. Bu ad daha sonra yönetici paneli, kullanıcı özeti ve son işlemler ekranlarında öncelikli olarak gösterilir. İsimler kalıcı olarak saklanır ve istenildiğinde değiştirilebilir veya kaldırılabilir.
