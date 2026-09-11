# Görev Maliyet Hesaplayıcı

Görev süresini ve maliyetini (amortisman + personel + yakıt) hesaplayan,
kullanıcı adı ve şifreyle açılan web sitesi.

## Adresler

| Adres | Giriş |
|-------|-------|
| Yan menüdeki **Görev Maliyet** | Home Assistant oturumu (ilk seferde bir kez site şifresi) |
| `http://homeassistant.local:8102` | kullanıcı adı ve şifre |
| KeenDNS adresi (HTTPS) | kullanıcı adı ve şifre |

## İlk kurulum

1. Eklentiyi başlatın.
2. **Günlük** sekmesinde `kurulum kodunu girin: 1234-5678` satırını bulun.
3. Siteyi açın; kodu, adınızı, kullanıcı adınızı ve şifrenizi girin.
4. **Ayarlar** sayfasında akaryakıt ilini, gün doğumu/batımı ilini ve aylık maaşı seçin.
5. Diğer kişileri sağ üstteki menüden **Kişiler / Şifreler** ile ekleyin veya
   **Üye ol** başvurularını onaylayın.

## Ayarlar

| Ayar | Açıklama |
|------|----------|
| `timezone` | Saat dilimi. Günlük piyasa verisi yenilemesi bu dilimde 17:00'de yapılır. |

## Veriler

Veritabanı `/share/gorev_maliyet/` altındadır; eklenti güncellense veya yeniden
kurulsa da silinmez. Euro kuru TCMB'den, akaryakıt fiyatı Petrol Ofisi'nden
otomatik alınır.

Ev dışından HTTPS ile erişim için depo belgelerindeki `DEPLOYMENT.md`
dosyasındaki KeenDNS adımlarını izleyin. 8102 portunu internete düz HTTP olarak
açmayın.
