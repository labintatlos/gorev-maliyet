# Test Talimatları - Görev Maliyet Telegram Botu v3.7

## 📋 Yeni Özellikler Özeti

### Eklenen Özellikler (Commit 1 & 2)

#### 1. Hesaplama Metrikler (calculator.py)
- ✅ `hourly_cost` - Saatlik ortalama maliyet
- ✅ `fuel_efficiency` - Yakıt verimliliği (L/saat)
- ✅ `amortization_percentage` - Amortisman yüzdesi
- ✅ `personnel_percentage` - Personel yüzdesi
- ✅ `fuel_percentage` - Yakıt yüzdesi

#### 2. Çevrimdışı Destek (webapp/)
- ✅ Service Worker (`service-worker.js`) - Offline cache
- ✅ localStorage yönetimi (`db.js`)
- ✅ Otomatik senkronizasyon (`sync.js`)

#### 3. Telegram Bot Menüsü (bot.py)
- ✅ MenuButtonWebApp - Mini App direkt açılır
- ✅ Hızlı menü butonları (🧮 Hesapla, 📚 Geçmiş, ⚙️ Ayarlar, 📡 Veriler)

#### 4. Mini App UI (webapp/)
- ✅ Toplam maliyet özeti kartı
- ✅ Paylaş/kopyala butonu
- ✅ Smooth animasyonlar

---

## 🧪 Test Adımları

### Hazırlık
1. Bot token'ını `.env` dosyasına ekleyin:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   AUTHORIZED_USER_IDS=your_user_id
   WEBAPP_URL=https://your-domain/webapp/  # (isteğe bağlı)
   ```

2. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

3. Bot'u başlatın:
   ```bash
   python bot.py
   ```

---

### Test Senaryoları

#### Test 1: Hesaplama Metriklerini Kontrol Et
1. `/start` komutunu çalıştırın
2. 🧮 Hesapla butonuna basın
3. Avara: 09:35, Aborda: 19:25, Personel: 4, Yakıt: 750L gibi örnek değerler girin
4. ✅ HESAPLA butonuna basın

**Kontrol Noktaları:**
- ✅ Sonuç mesajında şunları görmeli:
  - Saatlik ortalama maliyet (₺/saat)
  - Yakıt verimliliği (L/saat)
  - Maliyet yüzdeleri (amortisman %, personel %, yakıt %)

#### Test 2: Telegram Bot Menüsü
1. Bot başında `📱 Mini App Aç` butonu görülmeli
2. Alt menüdeki hızlı butonları test edin:
   - 🧮 Hesapla → hesaplama ekranı açılmalı
   - 📚 Geçmiş → geçmiş hesaplamalar görülmeli
   - ⚙️ Ayarlar → ayarlar menüsü açılmalı
   - 📡 Veriler → otomatik veriler gösterilmeli

#### Test 3: Mini App - Toplam Maliyet Özeti
1. Mini App'ı açın (📱 Hesapla butonundan)
2. Görev değerleri girin:
   - Avara: 09:00
   - Aborda: 14:00
   - Personel: 4
   - Yakıt: 500L

**Kontrol Noktaları:**
- ✅ Form altında "📊 Görev Özeti" kartı görülmeli
- ✅ Tahmini toplam maliyet gösterilmeli
- ✅ Toplam süre, yakıt ve verimlilik gösterilmeli
- ✅ 📋 Özeti Kopyala butonu çalışmalı
- ✅ Buton tıklanınca: "✓ Özet panoya kopyalandı!" mesajı görülmeli

#### Test 4: Çevrimdışı Mod (Offline)
1. Mini App'ı açın
2. Tarayıcı developer tools'da Network → Offline olarak ayarlayın
3. Hesaplama yapın ve Görevleri Hesapla butonuna basın

**Kontrol Noktaları:**
- ✅ "Çevrimdışı Mod" uyarısı gösterilmeli
- ✅ Hesaplama kaydedilmeli: "✓ Hesaplama kaydedildi!" mesajı
- ✅ localStorage'da veri tutulmalı

#### Test 5: Senkronizasyon
1. Offline modda 2-3 hesaplama kaydedin
2. Network → Online yapın

**Kontrol Noktaları:**
- ✅ "Senkronize ediliyor..." mesajı görülmeli
- ✅ Sonunda "Tüm hesaplamalar senkronize edildi ✓" mesajı
- ✅ Hesaplamalar bota gönderilmeli ve geçmiş'te görülmeli

#### Test 6: Animasyonlar
1. Mini App'ı açın
2. Form elemanları açılırken smooth slide-in animasyonu görülmeli
3. Butonlar hover'da hafif yukarı doğru hareket etmeli
4. Maliyet özeti kartı animasyon ile görünmeli

#### Test 7: Paylaş Butonu
1. Mini App'ı açın ve bilgiler girin
2. 📋 Özeti Kopyala butonuna basın
3. Telegram sohbetinde yapıştırın (Ctrl+V)

**Kontrol Noktaları:**
- ✅ Şu bilgiler panoya kopyalanmalı:
  ```
  📋 Görev Özeti
  📅 Tarih: YYYY-MM-DD
  👥 Personel: 4
  🛢 Yakıt: Dizel
  
  Görev 1:
    ⏱ 09:00 - 14:00 (5.00 saat)
    ⛽ 500L (~100.00L/saat)
  ```

---

## ✅ Test Kontrol Listesi

- [ ] Python syntax hatası yok
- [ ] JavaScript syntax hatası yok
- [ ] Bot başlıyor ve Telegram'da yanıt veriyor
- [ ] Hesaplama metrikler gösteriliyor
- [ ] Bot menü butonları çalışıyor
- [ ] Mini App açılıyor ve yükleniyor
- [ ] Maliyet özeti kartı gösteriliyoryor
- [ ] Paylaş butonu çalışıyor
- [ ] Offline mod çalışıyor
- [ ] Senkronizasyon çalışıyor
- [ ] Animasyonlar smooth görünüyor

---

## 🐛 Hata Bulma

Eğer hata görürseniz:

1. **Bot başlamıyor:**
   - Token doğru mu kontrol edin
   - Requirements yüklü mü: `pip list | grep python-telegram-bot`

2. **Mini App açılmıyor:**
   - WEBAPP_URL ayarlı mı kontrol edin
   - URL HTTPS olmalı

3. **Offline mod çalışmıyor:**
   - Service Worker kaydedildi mi: DevTools → Application → Service Workers
   - localStorage aktif mi: DevTools → Application → Local Storage

4. **Senkronizasyon başarısız:**
   - Console'da hata var mı (DevTools → Console)
   - Bot online durumdaki hesaplamayı kabul ediyor mu test edin

---

## 📝 Git Durumu

```bash
git log --oneline
# 273d3b2 Arayüz iyileştirmeleri: Bot menü, Mini App UI, animasyonlar
# c1be497 4 yeni özellik: saatlik maliyet, yakıt verimliği, offline, sync
# c5c5537 İlk commit
```

---

## 🚀 Hazır!

Bot artık tüm yeni özelliklerle hazır. Test sonrası production'a geçebilirsiniz!
