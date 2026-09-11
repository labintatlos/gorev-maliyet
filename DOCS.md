# Görev Maliyet Telegram Botu — v3.7.0

Home Assistant OS için yerel App/Add-on.

## 🆕 v3.7

- **Canlı maliyet önizlemesi:** Bot içindeki hesap paneli ve Mini App, değerler değiştikçe tahmini toplam maliyeti gösterir.
- **📊 İstatistikler (`/istatistik`):** Bu ay, son 7 gün, geçen ay ve tüm zamanlar özeti; geçen aya göre değişim ve maliyet dağılımı.
- **📤 CSV dışa aktarma (`/disaaktar`):** Geçmiş, Excel ile açılabilen dosya olarak gönderilir.
- **Yeni sonuç ekranı:** Toplam maliyet öne alındı; amortisman, personel ve yakıt payları çubuk grafikle gösterilir.
- **Günlük toplam:** Mini App'ten birden fazla görev gönderildiğinde toplam süre, yakıt, maliyet ve tüm GÖRRAP satırları tek mesajda.

## 📱 Telegram Mini App (Web App)

Telegram içinde tam ekran açılan Mini App ile görevler tek ekranda girilir:

- **Görev kartları:** Avara, Aborda ve yakıt litresi görev başına; tarih, yakıt türü ve personel ortak.
- **Canlı önizleme:** Bot, Mini App butonunun adresine güncel Euro kuru, il akaryakıt fiyatları, maaş ve gün doğumu/batımı saatlerini ekler. Toplam maliyet, maliyet dağılımı ve gündüz/gece süresi anında gösterilir. Kesin hesap bot tarafında yapılır.
- **Çevrimdışı kayıt:** Bağlantı yokken görevler cihazda saklanır ve daha sonra tek seferde bota gönderilir.
- **Kullanım:** `/start` sonrası klavye alanındaki `📱 Mini App Aç` butonu. Telegram, veri gönderimini yalnızca bu klavye butonundan açılışta desteklediği için sohbet menü butonu komut listesini açar.

### Mini App Yapılandırması
`config.yaml` / Add-on seçeneklerinde `webapp_url` alanına GitHub Pages veya kendi HTTPS web sunucunuzdaki URL girildiğinde tüm kullanıcılarda Mini App aktif olur. Bot, bu adrese önizleme parametrelerini kendisi ekler; mevcut sorgu parametreleri korunur.

## ⚙️ Sabit Ayarlar

Telegram ana menüsündeki **⚙️ Sabit Ayarlar** bölümünde kullanıcı bir kez şunları seçer:

- **Akaryakıt fiyat ili:** Petrol Ofisi benzin/motorin fiyatlarının alınacağı il (81 il).
- **Gün doğumu/batımı ili:** Gece ve gündüz görev süresinin hesaplanacağı il.
- **Aylık personel maaşı:** Personel maliyetinde kullanılacak aylık maaş.

Bu seçimler kullanıcı bazında SQLite veritabanında saklanır ve sonraki hesaplamalarda otomatik kullanılır.

Euro kuru TCMB'den, benzin ve motorin fiyatları seçili ilin Petrol Ofisi fiyat sayfasından otomatik alınır. Piyasa verileri bot açılışında ve her gün 17:00'de yenilenir.

## Güncelleme

Mevcut App'i kaldırmayın. Yeni klasör içeriğini mevcut `addons/gorev_maliyet_haos_addon` klasörünün üzerine yazın, App Store'da **Check for updates / Güncellemeleri kontrol et** deyip 3.7.0 sürümüne güncelleyin. Mini App'i ayrıca barındırıyorsanız `webapp/` klasörünü de güncelleyin.

## 👑 Yönetici Paneli

Ana menüdeki **👑 Yönetici Paneli** yalnızca yönetici hesabında görünür. Panel, bot kullanımına ilişkin işlem özetlerini ve kullanım istatistiklerini yalnızca yetkili yöneticiye sunar.

`admin_user_ids` boş bırakılırsa `authorized_user_ids` alanındaki **ilk ID** otomatik olarak yönetici kabul edilir.

### Kullanıcı İsimleri

**👑 Yönetici Paneli → 👥 Kullanıcılar** bölümünden yetkili kullanıcılara yönetici tarafından özel görünen ad verilebilir. Bu ad daha sonra yönetici paneli, kullanıcı özeti ve son işlemler ekranlarında öncelikli olarak gösterilir. İsimler kalıcı olarak saklanır ve istenildiğinde değiştirilebilir veya kaldırılabilir.
