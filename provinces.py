from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Province:
    name: str
    key: str
    latitude: float
    longitude: float

PROVINCES: tuple[Province, ...] = (
    Province('Adana', 'adana', 37.003277000000004, 35.3261219),
    Province('Adıyaman', 'adiyaman', 37.7640008, 38.2764355),
    Province('Afyonkarahisar', 'afyonkarahisar', 38.756850899999996, 30.538694399999997),
    Province('Aksaray', 'aksaray', 38.3705416, 34.026907),
    Province('Amasya', 'amasya', 40.6569451, 35.7727169),
    Province('Ankara', 'ankara', 39.921521899999995, 32.8537929),
    Province('Antalya', 'antalya', 36.9009641, 30.6954846),
    Province('Ardahan', 'ardahan', 41.1102966, 42.7035585),
    Province('Artvin', 'artvin', 41.160506, 41.839862700000005),
    Province('Aydın', 'aydin', 37.841300700000005, 27.832837400000003),
    Province('Ağrı', 'agri', 39.7201318, 43.050038799999996),
    Province('Balıkesir', 'balikesir', 39.6473917, 27.8879787),
    Province('Bartın', 'bartin', 41.6338394, 32.3384354),
    Province('Batman', 'batman', 37.7874104, 41.2573924),
    Province('Bayburt', 'bayburt', 40.25569, 40.224099),
    Province('Bilecik', 'bilecik', 40.1435101, 29.975291100000003),
    Province('Bingöl', 'bingol', 38.8851831, 40.4965998),
    Province('Bitlis', 'bitlis', 38.4002185, 42.1081317),
    Province('Bolu', 'bolu', 40.733295299999995, 31.6110479),
    Province('Burdur', 'burdur', 37.7248394, 30.288728600000002),
    Province('Bursa', 'bursa', 40.1826036, 29.067565500000004),
    Province('Denizli', 'denizli', 37.773483299999995, 29.087389399999996),
    Province('Diyarbakır', 'diyarbakir', 37.9167321, 40.2225658),
    Province('Düzce', 'duzce', 40.8458611, 31.164851000000002),
    Province('Edirne', 'edirne', 41.675932700000004, 26.5587225),
    Province('Elazığ', 'elazig', 38.5824771, 39.396179),
    Province('Erzincan', 'erzincan', 39.749605200000005, 39.4941023),
    Province('Erzurum', 'erzurum', 39.7581897, 41.4032241),
    Province('Eskişehir', 'eskisehir', 39.766681299999995, 30.5255947),
    Province('Gaziantep', 'gaziantep', 37.0611756, 37.3793085),
    Province('Giresun', 'giresun', 40.9148702, 38.3879289),
    Province('Gümüşhane', 'gumushane', 40.4617844, 39.475733899999994),
    Province('Hakkari', 'hakkari', 37.574898, 43.73766),
    Province('Hatay', 'hatay', 36.202593900000004, 36.1603945),
    Province('Isparta', 'isparta', 37.77035, 30.5556933),
    Province('Iğdır', 'igdir', 39.921566799999994, 44.0467724),
    Province('İstanbul', 'istanbul', 41.0096334, 28.9651646),
    Province('İzmir', 'izmir', 38.415342100000004, 27.144474),
    Province('Kahramanmaraş', 'kahramanmaras', 37.5812744, 36.927509),
    Province('Karabük', 'karabuk', 41.1110349, 32.619390100000004),
    Province('Karaman', 'karaman', 37.179244700000005, 33.222478100000004),
    Province('Kars', 'kars', 40.605158, 43.0961734),
    Province('Kastamonu', 'kastamonu', 41.3765359, 33.7770087),
    Province('Kayseri', 'kayseri', 38.7225274, 35.4874516),
    Province('Kilis', 'kilis', 36.718045000000004, 37.11688),
    Province('Kocaeli', 'kocaeli', 40.765382, 29.9406983),
    Province('Konya', 'konya', 37.8719963, 32.484401500000004),
    Province('Kütahya', 'kutahya', 39.4191505, 29.987292800000002),
    Province('Kırklareli', 'kirklareli', 41.7370223, 27.223552299999998),
    Province('Kırıkkale', 'kirikkale', 39.8485708, 33.5276222),
    Province('Kırşehir', 'kirsehir', 39.14611420000001, 34.1605587),
    Province('Malatya', 'malatya', 38.3483098, 38.3178715),
    Province('Manisa', 'manisa', 38.615502899999996, 27.4255716),
    Province('Mardin', 'mardin', 37.341485399999996, 40.7476249),
    Province('Mersin', 'mersin', 36.8117583, 34.6292679),
    Province('Muğla', 'mugla', 37.1642053, 28.2624288),
    Province('Muş', 'mus', 38.740370299999995, 41.4967451),
    Province('Nevşehir', 'nevsehir', 38.6223688, 34.713602200000004),
    Province('Niğde', 'nigde', 37.971207899999996, 34.6775534),
    Province('Ordu', 'ordu', 40.8292569, 37.4082764),
    Province('Osmaniye', 'osmaniye', 37.073671000000004, 36.255941),
    Province('Rize', 'rize', 41.022809, 40.519612),
    Province('Sakarya', 'sakarya', 40.7731834, 30.481606),
    Province('Samsun', 'samsun', 41.2889924, 36.329445899999996),
    Province('Siirt', 'siirt', 37.931282, 41.939840000000004),
    Province('Sinop', 'sinop', 42.0266698, 35.1506765),
    Province('Sivas', 'sivas', 39.7503572, 37.0145185),
    Province('Tekirdağ', 'tekirdag', 40.986222999999995, 27.513944),
    Province('Tokat', 'tokat', 40.327746999999995, 36.5539494),
    Province('Trabzon', 'trabzon', 41.0058605, 39.718092799999994),
    Province('Tunceli', 'tunceli', 39.1080631, 39.548196999999995),
    Province('Uşak', 'usak', 38.6710838, 29.407250899999998),
    Province('Van', 'van', 38.508360100000004, 43.374532200000004),
    Province('Yalova', 'yalova', 40.6556669, 29.272909100000003),
    Province('Yozgat', 'yozgat', 39.8205571, 34.8094917),
    Province('Zonguldak', 'zonguldak', 41.250324, 31.8389738),
    Province('Çanakkale', 'canakkale', 40.1534952, 26.4140933),
    Province('Çankırı', 'cankiri', 40.5971947, 33.6212704),
    Province('Çorum', 'corum', 40.54914960000001, 34.9602453),
    Province('Şanlıurfa', 'sanliurfa', 37.2595198, 39.0408174),
    Province('Şırnak', 'sirnak', 37.455253000000006, 42.5212049),
)

PROVINCE_BY_KEY = {p.key: p for p in PROVINCES}
PROVINCE_KEY_BY_NAME = {p.name.casefold(): p.key for p in PROVINCES}

def get_province(value: str) -> Province:
    key = value.strip().lower()
    if key in PROVINCE_BY_KEY:
        return PROVINCE_BY_KEY[key]
    folded = value.strip().casefold()
    mapped = PROVINCE_KEY_BY_NAME.get(folded)
    if mapped:
        return PROVINCE_BY_KEY[mapped]
    raise KeyError(f"Bilinmeyen il: {value}")
