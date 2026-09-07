# Changelog

## 3.6.0

- **Telegram Mini App (Web App) Desteği:**
  - Tek dokunuşla açılan şık, mobil uyumlu ve modern web form arayüzü (`webapp/`).
  - Form üzerinden Avara, Aborda, Görev Tarihi, Personel Sayısı, Yakıt Miktarı ve Yakıt Türü (Dizel/Benzin) hızlı seçimi.
  - Anlık görev süresi ve yaklaşık yakıt ağırlığı (kg) önizlemesi.
  - Telegram karanlık/aydınlık tema uyumu ve Haptic Feedback (dokunsal geri bildirim) desteği.
  - Telegram sol menü butonuna (`MenuButtonWebApp`) ve ana menüye doğrudan Mini App açma butonu eklendi.
  - `WEBAPP_URL` / `webapp_url` konfigürasyon seçeneği ile ücretsiz GitHub Pages veya HTTPS sunucu bağlantısı.
  - `/webapp` ve `/miniapp` komutları eklendi.

## 3.5.3

- Yönetim ekranında kullanıcı etiketleme ve görünüm iyileştirmeleri yapıldı.
- Kullanıcı listesi ve işlem özetlerinin okunabilirliği artırıldı.
- Genel performans ve kararlılık düzenlemeleri yapıldı.

## 3.5.2

- Genel performans ve kararlılık iyileştirmeleri yapıldı.
- Menü geçişleri ve veri erişimi optimize edildi.
- Yönetim ekranında kullanım ve işlem özetleri iyileştirildi.
- Arka plan veri yenileme akışı daha dayanıklı hale getirildi.
- Küçük arayüz ve hata yönetimi düzenlemeleri yapıldı.


## 3.5.0

- Yeni **Sabit Ayarlar** menüsü eklendi.
- Akaryakıt fiyat ili 81 il arasından seçilebilir ve kullanıcı bazında hatırlanır.
- Gün doğumu/batımı ili 81 il arasından seçilebilir ve kullanıcı bazında hatırlanır.
- Aylık personel maaşı Sabit Ayarlar'a taşındı ve kullanıcı bazında hatırlanır.
- Hesaplama ekranından maaş ve il ayarları kaldırıldı.
- Hesaplama ekranında yalnızca Avara, Aborda, Personel, Yakıt litresi ve Dizel/Benzin seçimi kaldı.
- Petrol Ofisi fiyat alma kodu seçilen ile göre genelleştirildi.
- Gün doğumu/batımı hesabı seçilen ilin koordinatlarına göre genelleştirildi.
- Günlük otomatik yenileme, kullanıcıların seçtiği akaryakıt illerini günceller.
- v3.4 geçmiş veritabanı otomatik yükseltilir; geçmiş silinmez.
- v3.4'teki son hesaplamanın maaşı ilk Sabit Ayar maaşı olarak devralınır.

## 3.4.0

- Gece/gündüz görev süresi ayrımı eklendi.
