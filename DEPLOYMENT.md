# Home Assistant OS Dağıtımı ve KeenDNS

## Mimari

| Giriş | Kimlik | Nereden |
|-------|--------|---------|
| **Web sitesi** (port 8102) | kullanıcı adı ve şifre | ev ağından `http://homeassistant.local:8102`, dışarıdan KeenDNS adresi |
| **Home Assistant paneli** (Ingress, port 8099) | HA oturumu | HA'nın sol menüsündeki **Görev Maliyet** |

İki giriş aynı süreçte, aynı veritabanıyla çalışır. 8102 portu Ingress
başlıklarına hiç güvenmez; kimlik yalnızca şifreyle verilen oturum çerezinden
gelir. 8099 portu dışarıya açılmaz ve `X-Remote-User-Name` başlığına yalnızca
Supervisor'ın adresinden gelen istekte güvenilir.

Veritabanı `/share/gorev_maliyet/gorev_maliyet.db` içindedir; eklenti
güncellense veya yeniden kurulsa da silinmez. Oturum imza anahtarı
(`session_secret`), kurulum kodu ve piyasa verisi önbelleği de aynı klasördedir.

Eklenti internete yalnızca şu iki adrese çıkar: `www.tcmb.gov.tr` (Euro kuru) ve
`www.petrolofisi.com.tr` (il akaryakıt fiyatları).

## 3.x (Telegram botu) → 4.0 geçişi

- 4.0 yeni bir eklentidir (`gorev_maliyet`); eski yerel Telegram eklentisinin
  (`gorev_maliyet_bot`) yerine kurulur. Telegram ayarları (`telegram_bot_token`,
  `authorized_user_ids`, `admin_user_ids`, `webapp_url`) kalkar.
- Eski Telegram geçmişi yeni siteye taşınmaz; site boş veritabanıyla başlar.
- Kişiler Telegram kimliğiyle değil, sitede açılan kullanıcı adıyla girer.
  Yönetici herkesi **Kişiler / Şifreler** ekranından ekler veya üyelik
  başvurularını onaylar. Her kişi il ve maaş ayarını **Ayarlar** sayfasında bir
  kez seçer.
- Yeni site doğrulandıktan sonra eski eklenti durdurulup kaldırılır.

## İlk kurulum

1. **Ayarlar → Eklentiler → Eklenti Mağazası → ⋮ → Depolar** bölümüne
   `https://github.com/labintatlos/gorev-maliyet` adresini ekleyin.
2. **Görev Maliyet Hesaplayıcı** eklentisini kurun ve başlatın.
3. **Günlük** sekmesinde `İlk yönetici henüz oluşturulmadı ... kurulum kodunu girin: 1234-5678` satırını bulun.
4. Siteyi açın, kodu, adınızı, kullanıcı adınızı ve şifrenizi girin.
5. **Ayarlar** sayfasında akaryakıt ilini, güneş ilini ve aylık maaşı seçin.
6. Sağ üstteki menüden **Kişiler / Şifreler** ile diğer kişileri ekleyin.

Kullanıcı adı 3-32 karakterdir (küçük harf, rakam, nokta, alt çizgi); şifre en
az 8 karakterdir. Aynı kullanıcı adıyla 15 dakika içinde 5 hatalı deneme
yapılırsa o ad bir süre için kilitlenir. Onay bekleyen 20 üyelik başvurusu
varken yeni başvuru alınmaz.

## KeenDNS ile HTTPS adres (Keenetic modem)

Keenetic modem, KeenDNS alan adı için HTTPS sertifikasını kendisi alır ve gelen
isteği ev ağındaki Raspberry Pi'ye iletir. Modemde port açmak gerekmez.

1. Modem arayüzünü açın (`http://192.168.1.1` veya `my.keenetic.net`).
2. **Ağ kuralları → Alan adı** bölümünde KeenDNS adınızın kayıtlı olduğunu
   görün (ör. `evim.keenetic.pro`).
3. **Ev ağındaki web uygulamalarına erişim** kısmında yeni kayıt ekleyin:

   | Alan | Değer |
   |------|-------|
   | Ad | `gorevmaliyet` → adres `gorevmaliyet.evim.keenetic.pro` olur |
   | Cihaz | Home Assistant (Raspberry Pi) |
   | Protokol | HTTP (dış tarafta HTTPS'i KeenDNS sağlar) |
   | Port | `8102` |
   | Yetkilendirme | Kapalı (site kendi şifresini ister) |

4. Telefonda mobil veriyle `https://gorevmaliyet.evim.keenetic.pro` adresini açın.

Modemde 8102 portunu doğrudan düz HTTP olarak internete açmayın: şifre
şifrelenmeden gider.

### KeenDNS bulut modunun kısıtları

Modemin genel IP'si yoksa KeenDNS "bulut" modunda çalışır. Bu modda:

- `http://` ile yazılan adres de siteye ulaşır. Site `http://` ile açılınca
  kendini `https://`'e taşır ve HSTS başlığı gönderir.
- Modem ziyaretçinin IP'sini iletmez; hatalı giriş kilidi bu yüzden kullanıcı
  adına göre çalışır.

## Kontrol

| İstek | Beklenen |
|-------|----------|
| `https://gorevmaliyet.evim.keenetic.pro/health` | `{"status":"ok"}` |
| `https://gorevmaliyet.evim.keenetic.pro/api/bootstrap` (giriş yapmadan) | `401` |

## Sorun giderme

- **Kurulum kodunu bulamıyorum:** Eklentiyi yeniden başlatın; etkin yönetici
  yoksa kod her açılışta günlüğe yeniden yazılır.
- **Şifremi unuttum:** Başka bir yönetici **Kişiler / Şifreler** ekranından
  yeni şifre verebilir.
- **"Euro veya akaryakıt fiyatı alınamadı":** **Ayarlar → Otomatik veriler →
  Şimdi yenile**. Sorun sürerse eklenti günlüğünde TCMB/Petrol Ofisi hatasına
  bakın; kaynak sayfa değişmiş olabilir (`python tools/check_market.py`).
