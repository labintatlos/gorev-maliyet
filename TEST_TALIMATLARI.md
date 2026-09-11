# Test Talimatları - Görev Maliyet Telegram Botu v3.7

## Hazırlık

1. Ortam değişkenlerini ayarlayın (`.env` veya Home Assistant seçenekleri):
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   AUTHORIZED_USER_IDS=your_user_id
   WEBAPP_URL=https://your-domain/webapp/   # isteğe bağlı, HTTPS olmalı
   ```
2. Bağımlılıkları yükleyin: `pip install -r requirements.txt`
3. Botu başlatın: `python bot.py`
4. Mini App kullanılacaksa `webapp/` klasörünün güncel halini HTTPS sunucuya yükleyin.

---

## Test Senaryoları

### 1. Ana menü ve komutlar
1. `/start` yazın.
- ✅ Klavyede `📱 Mini App Aç` (WEBAPP_URL varsa), `🧮 Hesapla`, `📚 Geçmiş`, `⚙️ Ayarlar`, `📡 Veriler`, `📊 İstatistik` görünür.
- ✅ Menü mesajında Euro, il motorin/benzin fiyatı ve bu ayın görev/maliyet özeti vardır.
- ✅ Sohbetin sol altındaki menü butonu komut listesini açar (`/istatistik`, `/disaaktar` dahil).
- ✅ Rastgele bir metin yazıldığında bot "tanıyamadım" deyip menüyü gösterir.

### 2. Bot içi hesaplama
1. `🧮 Hesapla` → saatleri ve yakıtı butonlarla değiştirin.
- ✅ Panelde süre ve **Tahmini toplam** her değişiklikte güncellenir.
- ✅ Avara = Aborda yapıldığında panelde uyarı çıkar; `✅ HESAPLA` uyarı penceresi gösterir, kayıt oluşmaz.
2. Geçerli değerlerle `✅ HESAPLA`.
- ✅ Sonuçta TOPLAM, saatlik ortalama, üç maliyet kalemi için `█░` çubuğu ve `%` payı, GÖRRAP satırı vardır.
- ✅ Sayılar Türkçe biçimdedir (`₺5.486,83`, `76,27 L/saat`).

### 3. Mini App — önizleme
1. `/start` sonrası klavyedeki `📱 Mini App Aç` ile açın.
- ✅ Üst şeritte Euro, il yakıt fiyatı ve maaş; alt başlıkta gün doğumu/batımı görünür.
- ✅ Görev kartında 24 saatlik çizelge: gece/gündüz bantları ve görev aralığı.
- ✅ Saat/yakıt/personel değiştirildikçe kart maliyeti, özet toplamı, dağılım çubuğu ve Telegram ana butonu (`✅ HESAPLA · ₺…`) güncellenir; kartlar titremez.
- ✅ Benzin seçildiğinde fiyat şeridi ve maliyetler benzin fiyatına geçer.
- ✅ Gece yarısını geçen görev (ör. 22:00–01:30) çizelgede iki parça görünür.
2. Avara ve Aborda'yı aynı yapıp gönderin.
- ✅ Kart kırmızı çerçeveyle sallanır, uyarı çıkar, veri gönderilmez.
3. `📋 Özeti kopyala`.
- ✅ Görevler, süreler, litre ve tahmini maliyet panoya kopyalanır.

### 4. Mini App — gönderim
1. İki görev ekleyip ana butona basın.
- ✅ Mini App kapanır; bot her görev için sonuç mesajı ve ardından **🧾 GÜNLÜK TOPLAM** mesajı gönderir.
- ✅ `📋 Tüm GÖRRAP satırlarını kopyala` butonu tüm satırları kopyalar.
- ✅ Bot tarafındaki tutarlar Mini App önizlemesiyle aynıdır (fiyatlar değişmediyse).

### 5. Mini App — çevrimdışı
1. Mini App açıkken cihazın internetini kapatın.
- ✅ Üstteki durum rozeti `Çevrimdışı` olur, ana buton `💾 ÇEVRİMDIŞI KAYDET` yazar.
2. Görevi gönderin.
- ✅ "Çevrimdışı kaydedildi" bildirimi; **📦 Bekleyen kayıtlar** kartı belirir.
3. İnterneti açın.
- ✅ "Bağlantı geri geldi" bildirimi; `📤 Bota gönder` aktifleşir.
4. `📤 Bota gönder`.
- ✅ Bot "N bekleyen Mini App kaydı alındı" yazar ve her kaydı `[1/N]` önekiyle hesaplar.

### 6. Yanlış açılış
1. Mini App'i bir bağlantıdan veya inline butondan açın.
- ✅ "Klavye butonundan açın" ekranı ve `Pencereyi kapat` butonu görünür.

### 7. Geçmiş, istatistik, dışa aktarma
1. `📚 Geçmiş`.
- ✅ Satırlar `#no · görev tarihi · 09:35–19:25 · ₺tutar` biçimindedir.
- ✅ Bir kayıt açılınca sonuç ekranıyla aynı düzen, `🗑 Bu kaydı sil` onaylı çalışır.
2. `📊 İstatistikler`.
- ✅ Bu ay / son 7 gün / geçen ay / tüm zamanlar blokları ve maliyet dağılımı görünür.
3. `📤 CSV indir` veya `/disaaktar`.
- ✅ `.csv` dosyası gelir; Excel'de Türkçe karakterler ve sayılar doğru sütunlarda açılır.

### 8. Sabit ayarlar
1. Maaşı ve akaryakıt ilini değiştirin, `/start` yazıp Mini App'i yeniden açın.
- ✅ Mini App önizlemesi yeni maaş ve il fiyatını kullanır.

---

## ✅ Kontrol Listesi

- [ ] `python -m py_compile bot.py calculator.py market_data.py solar_time.py provinces.py`
- [ ] `node --check webapp/app.js webapp/calc.js webapp/db.js webapp/sync.js webapp/service-worker.js`
- [ ] Bot başlıyor, `/start` menüsü ve komut listesi görünüyor
- [ ] Bot içi hesaplama, sıfır süre uyarısı
- [ ] Mini App önizlemesi, çoklu görev gönderimi ve günlük toplam
- [ ] Çevrimdışı kayıt ve toplu gönderim
- [ ] Geçmiş, tek kayıt silme, istatistikler, CSV
- [ ] Açık ve koyu temada görünüm

---

## 🐛 Hata Bulma

1. **Bot başlamıyor:** Token ve `AUTHORIZED_USER_IDS` doğru mu? `pip list | grep python-telegram-bot`
2. **Mini App açılmıyor:** `WEBAPP_URL` HTTPS mi ve `webapp/` dosyaları güncel mi?
3. **Mini App'te maliyet önizlemesi yok:** Klavye eski sürümden kalmış olabilir; `/start` yazıp klavyeyi yenileyin.
4. **Veri bota gitmiyor:** Mini App'in sohbet klavyesindeki `📱 Mini App Aç` butonundan açıldığından emin olun.
5. **Eski Mini App sürümü görünüyor:** Service worker güncellemesi için Mini App'i kapatıp yeniden açın.
