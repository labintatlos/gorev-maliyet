# Bu depoda çalışan yapay zekâ asistanları için

Bu dosya Claude Code, ChatGPT/Codex veya başka bir asistanın işi kaldığı yerden
devralabilmesi için yazılmıştır. Kullanıcı Türkçe konuşur; arayüz metinleri ve
kullanıcıya verilen cevaplar Türkçedir.

## Proje

Görev Maliyet Hesaplayıcı: avara/aborda saatleri, yakıt ve personel bilgisiyle
görev süresini ve maliyetini (amortisman + personel + yakıt) hesaplayan,
GÖRRAP satırını üreten web sitesi. Home Assistant OS
üzerinde (Raspberry Pi 5) bir eklenti olarak çalışır ve kullanıcı adı/şifreyle
açılır. Eskiden Telegram botuydu (3.x); 4.0.0 ile tamamen web sitesine geçildi.
Giriş, üyelik, kişiler ve dağıtım düzeni kullanıcının **Su Ürünleri Denetim
Asistanı** ve **Aile Bütçe Takip** siteleriyle aynıdır.

Mimari ve dosya yapısı için [README.md](README.md), dağıtım ve KeenDNS için
[DEPLOYMENT.md](DEPLOYMENT.md).

## Değişmez kurallar

1. **Çalışan özellikler korunur.** Mevcut davranış gereksinimdir. Değişiklik
   küçük adımlarla yapılır ve her adım eskisiyle karşılaştırılarak doğrulanır.
   Hesap sonuçları `calculator.py` formülleriyle birebir kalmalıdır. Arayüzde ve
   belgelerde "Excel" ifadesi/vurgusu kullanılmaz (kullanıcı kararı, 4.0.1);
   `smoke_test.py` bunu denetler.
2. **Çalıştırmadan "bitti" denmez.** Kod gerçekten çalıştırılmadan ve test
   çıktısı görülmeden hiçbir iş "tamamlandı / test edildi" diye raporlanmaz.
   Doğrulanamayan kısım açıkça söylenir.
3. **Teslim = push + sürüm artışı.** Home Assistant güncellemeyi yalnızca
   GitHub'daki `gorev_maliyet/config.yaml` içindeki `version` alanından görür.
   Her push'ta (yalnızca doküman değişse bile) sürüm artırılır, commit
   `origin/master`'a gönderilir.
4. **Çalışma düzeni:** Kullanıcı istekleri sırasız verir; asistan sıralar,
   her adımı bitirip pushlar ve bir sonraki adıma geçmeden onay bekler.
5. **İstenmeyen mekanizma eklenmez.**
6. **Depo herkese açıktır (public).** Şifre, API anahtarı, erişim anahtarı,
   KeenDNS adresi, MAC adresi ve benzeri hiçbir özel bilgi commit edilmez.
   Erişim bilgisi gerektiğinde kullanıcıdan `C:\Users\cemci\erisim_bilgileri.txt`
   dosyasına yazması istenir (sohbete şifre yazdırılmaz) ve iş bitince dosyayı
   silmesi önerilir.
7. **Canlı sisteme bağlanarak çalışılır.** Home Assistant ve Keenetic modeme
   doğrudan erişilir; dışa aktarılmış dosyalar üzerinden tahmin yürütülmez.
   Canlı sistemde değişiklik (eklenti kurma/kaldırma, modem kaydı) kullanıcı
   onayıyla yapılır.
8. Kullanıcıya zamir gerekiyorsa cinsiyet varsayılmaz.

## Yerel notlar (depoda yok)

Bu bilgisayarda depo klasöründeki `yerel/` dizini `.gitignore` ile dışarıda
tutulur. Varsa önce `yerel/NOTLAR.md` dosyasını okuyun (canlı adresler, KeenDNS
kaydı, Home Assistant güncelleme varlığı). Keenetic RCI ve Home Assistant API
ayrıntıları Su Ürünleri deposundaki `yerel/NOTLAR.md` ile aynıdır.

## Çalıştırma ve doğrulama

Eklenti hiçbir paket gerektirmez (Python 3.11+ standart kütüphanesi).

```bash
python tools/smoke_test.py      # sunucuyu başlatır, bütün API akışlarını dener → errors: 0
python tools/check_market.py    # TCMB ve Petrol Ofisi'nden gerçek veri çeker (internet gerekir)
python tools/browser_check.py   # gerçek Chrome'da gezinir, ekran görüntüsü alır (pip install websockets)
```

`smoke_test.py` geçici veritabanı ve sabit piyasa verisiyle çalışır; hesap
sonuçlarını Telegram botunda doğrulanmış değerlerle karşılaştırır (ör. 09:35–19:25,
4 kişi, 750 L, EUR 48,1234, motorin 62,45 → ₺53.953,82). Arayüz değişikliklerinde
`browser_check.py` ile telefon ve masaüstü genişliğinde bakılmalıdır.

`static/calc.js` canlı önizleme için `calculator.py` formüllerinin JavaScript
kopyasıdır; formül değişirse ikisi birlikte değişmelidir.

## Dağıtım adımları

1. Değişikliği yap, `python tools/smoke_test.py` çalıştır, `errors: 0` gör.
2. `gorev_maliyet/config.yaml` içindeki `version` değerini artır, `CHANGELOG.md`'ye yaz.
3. Commit et ve `git push origin master`.
4. Home Assistant'ta eklenti mağazasını yenile ve güncellemeyi kur.
5. Canlı sitede `/health` ve değişen davranışı kontrol et.

## Bilinen kısıtlar

- Site dışarıya Keenetic KeenDNS **bulut modu** ile açılır (modemin genel IP'si
  yok). Tünel `X-Forwarded-For` / `X-Forwarded-Proto` iletmez ve `http://`
  isteklerini de siteye geçirir:
  - Her istek sunucuya modemin adresinden gelir; hatalı giriş kilidi fiilen
    kullanıcı adına göre çalışır.
  - `http://` → `https://` yönlendirmesini `static/app.js` en başta yapar ve
    8102 portu `Strict-Transport-Security` gönderir. Bu kod silinmemelidir.
  - Oturum çerezinin `Secure` bayrağı tarayıcının POST isteğine eklediği
    `Origin` başlığına bakar.
- 8099 (Ingress) portu dışarı açılmaz; `X-Remote-User-Name` başlığına yalnızca
  Supervisor adresinden gelen istekte güvenilir.
- İçerik Güvenlik Politikası satır içi stile izin vermez; `app.js` genişlik gibi
  değerleri `element.style` ile verir, HTML metnine `style="..."` yazılmaz.
- Piyasa verisi açılışta ve her gün 17:00'de yenilenir; kaynak ulaşılamazsa son
  başarılı değer korunur. Petrol Ofisi sayfa yapısı değişirse
  `tools/check_market.py` hata verir.

## Yol haritası

| # | Adım | Durum |
|---|------|-------|
| 1 | Telegram botundan web sitesine geçiş: giriş/üyelik, hesaplama, geçmiş, istatistik, CSV, ayarlar, yönetim | ✅ 4.0.0 (yerelde doğrulandı) |
| 2 | GitHub deposu, Home Assistant'a eklenti deposu olarak ekleme ve kurulum, ilk yönetici | ✅ 4.0.0 |
| 3 | KeenDNS alt adresi (HTTPS) ve dışarıdan erişim kontrolü | ✅ 4.0.0 |
| 4 | Eski Telegram botu eklentisini (`local_gorev_maliyet_bot`) durdurup kaldırma | ✅ kullanıcı onayıyla kaldırıldı |
| 5 | Arayüz ve belgelerden "Excel" vurgusunu kaldırma | ✅ 4.0.1 |
