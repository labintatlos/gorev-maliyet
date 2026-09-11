# Changelog

## 4.1.0

- Giriş ekranı, üst menü ve sayfa yüzeyleri yenilendi; denizcilik renkleri açık ve koyu görünümde korundu.
- Maliyet özeti lacivert kart, belirgin toplam ve daha okunur dağılımla öne çıkarıldı. Piyasa verileri sade bir bilgi bandında toplandı.
- Hesaplama formu açıklamalı “Görev bilgileri” ve “Seyir ve yakıt” bölümlerine ayrıldı; saat alanları büyütüldü, hızlı doldurma düğmeleri telefonda satıra sığacak şekilde düzenlendi.
- Geçmiş, istatistik ve sonuç raporlarında tutarların vurgusu, kart aralıkları ve bölüm ayrımları iyileştirildi. Personel ve yakıt sayı alanlarına klavye odağı eklendi.
- Tabletlerde menü taşması düzeltildi; 900 piksel ve altında alt gezinme kullanılır.
- Tarayıcı kontrolü yatay taşmayı denetler; 320, 768 ve 1024 piksel ile karanlık masaüstü görüntüleri eklendi. Ekran görüntülerinden önce sayfa başına dönülür.
- `python tools/smoke_test.py` ve `python tools/browser_check.py yerel/ui-after`: `errors: 0`. Hesaplama formülleri değişmedi; referans toplam ₺53.953,82 korundu.

## 4.0.2

- Görsel/arayüz cilası: sekme değişince sayfa içeriği yumuşak yükselerek belirir, bildirim ve bekleme katmanı animasyonlu açılır, düğmelerde masaüstünde ince bir hover gölgesi var.
- Su Ürünleri ve Aile Bütçe siteleriyle aynı `rise` hareket eğrisi kullanılır; üçü arasında ortak bir görsel/hareket dili kuruldu.
- `tools/smoke_test.py` (errors: 0) ve `tools/browser_check.py` ile telefon/masaüstü, açık/koyu temada doğrulandı; konsol hatası veya CSP ihlali yok.

## 4.0.1

- Giriş ekranı, Geçmiş ve Ayarlar sayfalarındaki "Excel" ifadeleri kaldırıldı: dışa aktarma düğmesi **CSV indir**, ayarlardaki kart **Hesap sabitleri** oldu.
- Belgeler aynı şekilde güncellendi; duman testi arayüzde bu ifadenin geri gelmediğini denetler.
- Eski Görev Maliyet Telegram Botu eklentisi Home Assistant'tan kaldırıldı.

## 4.0.0

Telegram botundan **web sitesine** geçiş. Proje artık Su Ürünleri ve Aile Bütçe siteleriyle aynı düzende, kullanıcı adı ve şifreyle açılan bir Home Assistant eklentisidir (`gorev_maliyet`, port 8102, Home Assistant paneli).

### Site
- Giriş, **Üye ol** (yönetici onaylı), **Şifremi unuttum**, **Kişiler / Şifreler**, **Sorun bildir**, işlem kayıtları ve kurulum koduyla ilk yönetici.
- **Hesapla:** Mini App'in hesap ekranı sitenin ana sayfası oldu. Euro, il akaryakıt fiyatı, maaş ve gün doğumu/batımı sunucudan canlı gelir; toplam maliyet ve dağılım değerler değiştikçe görünür. Birden fazla görev tek seferde hesaplanır.
- **Sonuç raporu:** toplam, dağılım çubuğu, saatlik ortalama, yakıt ağırlığı/verimi, kullanılan veriler, GÖRRAP satırını kopyalama; çoklu görevde günlük toplam.
- **Geçmiş:** kayıt detayı, bu değerlerle yeniden hesaplama, kayıt silme, geçmişi temizleme, CSV çıktısı.
- **İstatistik:** bu ay, son 7 gün, geçen ay, tüm zamanlar ve maliyet dağılımı.
- **Ayarlar:** akaryakıt ili, güneş ili, aylık maaş; otomatik verileri görme ve elle yenileme; hesap sabitleri.
- **Yönetim:** bugünkü/toplam hesaplama, son 7 gün grafiği, kişi başına kullanım, açık sorun bildirimleri, son işlemler.
- Aydınlık/karanlık görünüm, telefonda alt gezinme çubuğu, bağlantı yokken hesaplamayı cihazda bekletme.

### Altyapı
- Yalnızca Python standart kütüphanesi: `python-telegram-bot`, `requests` ve `beautifulsoup4` bağımlılıkları kalktı; TCMB ve Petrol Ofisi verisi `urllib`/`html.parser` ile alınır.
- Veritabanı `/share/gorev_maliyet/` altında; eklenti yeniden kurulsa da silinmez.
- Kişiler arası veri yalıtımı, CSRF başlığı, İçerik Güvenlik Politikası, hatalı giriş kilidi, şifre değişince diğer oturumların kapanması.
- `tools/smoke_test.py` (104 kontrol), `tools/check_market.py` (canlı veri) ve `tools/browser_check.py` (gerçek tarayıcı) doğrulama betikleri.

### Kaldırılanlar
- Telegram botu, Telegram ayarları ve Telegram Mini App. Eski Telegram geçmişi yeni siteye taşınmaz.

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
