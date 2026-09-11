from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Union

NumberLike = Union[str, int, float, Decimal]

DAILY_AMORTIZATION_EUR = Decimal("70")
DIESEL_DENSITY_KG_PER_L = Decimal("0.82")
GASOLINE_DENSITY_KG_PER_L = Decimal("0.745")
# Geriye dönük uyumluluk: eski isim dizel katsayısını işaret eder.
FUEL_DENSITY_KG_PER_L = DIESEL_DENSITY_KG_PER_L
HOURS_PER_MONTH = Decimal("720")  # Excel: 30 gün x 24 saat


@dataclass(frozen=True)
class CalculationResult:
    departure: str
    arrival: str
    duration_minutes: int
    duration_hours: Decimal
    daily_amortization_eur: Decimal
    hourly_amortization_eur: Decimal
    eur_try: Decimal
    amortization_cost_try: Decimal
    monthly_salary_try: Decimal
    hourly_salary_try: Decimal
    personnel_count: int
    personnel_cost_try: Decimal
    fuel_liters: Decimal
    fuel_kilograms: Decimal
    fuel_price_try_per_liter: Decimal
    fuel_cost_try: Decimal
    total_cost_try: Decimal

    @property
    def duration_text(self) -> str:
        hours, minutes = divmod(self.duration_minutes, 60)
        return f"{hours} SA {minutes:02d} DA"

    @property
    def gorrap_line(self) -> str:
        # Excel A21'deki MALİYET-1/... çıktı düzeni korunur.
        return (
            f"MALİYET-1/{self.duration_text}/"
            f"{format_tr(self.amortization_cost_try)} TL/"
            f"{format_tr(self.personnel_cost_try)} TL/"
            "0 TL/0 TL/"
            f"{format_tr(self.fuel_cost_try)} TL/"
            f"{format_tr(self.total_cost_try)} TL//"
        )

    @property
    def hourly_cost(self) -> Decimal:
        """Saatlik ortalama maliyet (TL/saat)"""
        if self.duration_hours == 0:
            return Decimal("0")
        return quantize_money(self.total_cost_try / self.duration_hours)

    @property
    def fuel_efficiency(self) -> Decimal:
        """Yakıt verimliliği (litre/saat)"""
        if self.duration_hours == 0:
            return Decimal("0")
        return (self.fuel_liters / self.duration_hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def amortization_percentage(self) -> Decimal:
        """Toplam maliyetin % kaçı amortizasyondan"""
        if self.total_cost_try == 0:
            return Decimal("0")
        return (self.amortization_cost_try / self.total_cost_try * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    @property
    def personnel_percentage(self) -> Decimal:
        """Toplam maliyetin % kaçı personelden"""
        if self.total_cost_try == 0:
            return Decimal("0")
        return (self.personnel_cost_try / self.total_cost_try * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    @property
    def fuel_percentage(self) -> Decimal:
        """Toplam maliyetin % kaçı yakıttan"""
        if self.total_cost_try == 0:
            return Decimal("0")
        return (self.fuel_cost_try / self.total_cost_try * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def parse_decimal(value: NumberLike) -> Decimal:
    """Türkçe/İngilizce sayı girişlerini Decimal'e çevirir.

    Desteklenen örnekler: 53,88 | 53.88 | 105000 | 105.000 | 1.234,56 | 1,234.56
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))

    text = str(value).strip().replace(" ", "").replace("₺", "").replace("€", "")
    if not text:
        raise ValueError("Boş sayı girilemez.")

    if "," in text and "." in text:
        # En sağdaki ayırıcıyı ondalık ayırıcı kabul et.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # Türkçe ondalık giriş: 53,88
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") == 1:
        left, right = text.split(".")
        integer = left.lstrip("+-")
        # 105.000 gibi tipik binlik girişini de kabul et; 0.745 gibi değerler ondalık kalır.
        if integer.isdigit() and not integer.startswith("0") and right.isdigit() and len(right) == 3 and len(integer) <= 3:
            text = left + right
    elif text.count(".") > 1:
        text = text.replace(".", "")

    try:
        return Decimal(text)
    except Exception as exc:
        raise ValueError("Geçerli bir sayı girin. Örnek: 53,88") from exc


def parse_time_hhmm(value: str) -> tuple[int, int]:
    text = value.strip().replace(".", ":")
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError("Saati SS:DD biçiminde girin. Örnek: 09:35")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError("Saati SS:DD biçiminde girin. Örnek: 09:35") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Saat 00:00 ile 23:59 arasında olmalıdır.")
    return hour, minute


def normalize_time(value: str) -> str:
    hour, minute = parse_time_hhmm(value)
    return f"{hour:02d}:{minute:02d}"


def duration_minutes(departure: str, arrival: str) -> int:
    """Excel MOD(B4-A4,1) mantığı: gece yarısı geçişini destekler."""
    dep_h, dep_m = parse_time_hhmm(departure)
    arr_h, arr_m = parse_time_hhmm(arrival)
    dep_total = dep_h * 60 + dep_m
    arr_total = arr_h * 60 + arr_m
    return (arr_total - dep_total) % (24 * 60)


def calculate(
    *,
    departure: str,
    arrival: str,
    eur_try: NumberLike,
    monthly_salary_try: NumberLike,
    personnel_count: int,
    fuel_liters: NumberLike,
    fuel_price_try_per_liter: NumberLike,
    daily_amortization_eur: NumberLike = DAILY_AMORTIZATION_EUR,
    fuel_density_kg_per_l: NumberLike = FUEL_DENSITY_KG_PER_L,
) -> CalculationResult:
    if personnel_count < 0:
        raise ValueError("Personel sayısı negatif olamaz.")

    eur_try_d = parse_decimal(eur_try)
    salary_d = parse_decimal(monthly_salary_try)
    liters_d = parse_decimal(fuel_liters)
    fuel_price_d = parse_decimal(fuel_price_try_per_liter)
    daily_amort_d = parse_decimal(daily_amortization_eur)
    density_d = parse_decimal(fuel_density_kg_per_l)

    for name, val in (
        ("Euro kuru", eur_try_d),
        ("Aylık maaş", salary_d),
        ("Yakıt litresi", liters_d),
        ("Litre fiyatı", fuel_price_d),
        ("Günlük amortisman", daily_amort_d),
        ("Yakıt yoğunluğu", density_d),
    ):
        if val < 0:
            raise ValueError(f"{name} negatif olamaz.")

    mins = duration_minutes(departure, arrival)
    hours = Decimal(mins) / Decimal(60)

    hourly_amort = daily_amort_d / Decimal(24)
    amort_cost = hourly_amort * eur_try_d * hours

    hourly_salary = salary_d / HOURS_PER_MONTH
    personnel_cost = hourly_salary * Decimal(personnel_count) * hours

    fuel_kg = liters_d * density_d
    fuel_cost = liters_d * fuel_price_d

    total = amort_cost + personnel_cost + fuel_cost

    return CalculationResult(
        departure=normalize_time(departure),
        arrival=normalize_time(arrival),
        duration_minutes=mins,
        duration_hours=hours,
        daily_amortization_eur=daily_amort_d,
        hourly_amortization_eur=hourly_amort,
        eur_try=eur_try_d,
        amortization_cost_try=amort_cost,
        monthly_salary_try=salary_d,
        hourly_salary_try=hourly_salary,
        personnel_count=personnel_count,
        personnel_cost_try=personnel_cost,
        fuel_liters=liters_d,
        fuel_kilograms=fuel_kg,
        fuel_price_try_per_liter=fuel_price_d,
        fuel_cost_try=fuel_cost,
        total_cost_try=total,
    )


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_tr(value: NumberLike, decimals: int = 2) -> str:
    d = parse_decimal(value)
    q = d.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    raw = f"{q:,.{decimals}f}"
    # 68,563.92 -> 68.563,92
    return raw.replace(",", "_").replace(".", ",").replace("_", ".")
