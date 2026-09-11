# Changelog

## 3.7.0

### Telegram bot
- Ana menü güncel Euro ve akaryakıt fiyatlarını, bu ayın görev sayısını ve toplam maliyetini gösterir; butonlar iki sütunlu düzene alındı.
- Hesap paneli girilen değerlerle **görev süresini ve tahmini toplam maliyeti** canlı gösterir. Avara ve Aborda aynıysa uyarır ve hesaplamayı engeller.
- Sonuç ve geçmiş kaydı ekranları yenilendi: toplam maliyet öne alındı, amortisman/personel/yakıt payları çubuk grafikle gösterilir, saatlik maliyet ve yakıt verimi Türkçe sayı biçimindedir.
- Mini App'ten birden fazla görev gönderildiğinde görev sonuçlarının ardından **günlük toplam** mesajı ve tüm GÖRRAP satırlarını tek dokunuşla kopyalama butonu gelir.
- Yeni **📊 İstatistikler** ekranı (`/istatistik`): bu ay, son 7 gün, geçen ay ve tüm zamanlar; geçen aya göre değişim ve maliyet dağılımı.
- Geçmiş **CSV (Excel) olarak indirilebilir** (`/disaaktar`) ve tek tek kayıt silinebilir.
- Geçmiş listesi görev tarihini ve Avara–Aborda aralığını gösterir.
- Komut listesi Telegram menüsüne eklendi; tanınmayan mesajlara menüyle yanıt verilir; beklenmeyen hatalar kullanıcıya bildirilir.

### Mini App
- Arayüz baştan tasarlandı: Telegram temasına uyumlu açık/koyu görünüm, üstte güncel fiyat şeridi, görev kartları, özet kartı.
- **Canlı maliyet önizlemesi:** bot, klavye butonunun adresine güncel Euro kuru, il fiyatları, maaş ve gün doğumu/batımı saatlerini ekler; Mini App toplam maliyeti, dağılımı ve görev başı maliyeti anında hesaplar (hesap çekirdeği `calculator.py` ile birebir aynıdır).
- Her görevde 24 saatlik **gündüz/gece zaman çizelgesi**.
- Değer değişikliklerinde kartlar yerinde güncellenir; +/- butonlarında titreme ve odak kaybı yok. Hatalı görev kartı işaretlenir.
- Telegram ana butonu tahmini toplamı gösterir.
- Çevrimdışı kayıt yeniden yazıldı: bağlantı yokken kayıt cihazda saklanır, "Bota gönder" ile tek seferde toplu iletilir (bot `batch` biçimini işler).
- Service worker: sayfa için önce ağ, dosyalar için önbellek; parametreli adresler çevrimdışı da açılır.

### Düzeltmeler
- Menü butonundan açılan Mini App veri gönderemediği halde sohbet menüsüne "📱 Hesapla" butonu kuruluyordu; menü butonu artık komut listesini açar.
- Mini App'teki sabit `₺2500/saat` tahmini kaldırıldı; süre 0 iken görülen `Infinity L/sa` düzeltildi.
- `sync.js` her açılışta hata veriyor ve bota, botun tanımadığı bir veri biçimi gönderiyordu.
- Geçmişte üç ondalıklı tutarlar (ör. 10,5 L × 62,45 = 655,725) binlik ayırıcılı sanılıp yanlış gösteriliyordu.
- `parse_decimal` `0.745` gibi girişleri 745 olarak okuyordu.
- Veritabanı bağlantıları artık her işlemden sonra kapatılıyor.
- Geçersiz `HapticFeedback.impactOccurred('selection')` çağrısı düzeltildi.

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
