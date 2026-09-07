from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from provinces import get_province

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Istanbul")
TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
PETROL_OFISI_URL = "https://www.petrolofisi.com.tr/akaryakit-fiyatlari/{slug}-akaryakit-fiyatlari"
USER_AGENT = "Mozilla/5.0 (compatible; GorevMaliyetBot/3.5; +HomeAssistant)"
HTTP_TIMEOUT_SECONDS = 25


@dataclass
class FuelProvinceSnapshot:
    province_name: str
    diesel_price_try_per_liter: str | None = None
    gasoline_price_try_per_liter: str | None = None
    source_date: str | None = None
    source_name: str | None = None
    updated_at: str | None = None

    @property
    def diesel_decimal(self) -> Decimal | None:
        return Decimal(self.diesel_price_try_per_liter) if self.diesel_price_try_per_liter else None

    @property
    def gasoline_decimal(self) -> Decimal | None:
        return Decimal(self.gasoline_price_try_per_liter) if self.gasoline_price_try_per_liter else None

    def price_for(self, fuel_type: str) -> Decimal | None:
        return self.gasoline_decimal if fuel_type == "gasoline" else self.diesel_decimal


@dataclass
class MarketSnapshot:
    eur_try: str | None = None
    eur_source_date: str | None = None
    eur_updated_at: str | None = None
    fuel_prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_refresh_at: str | None = None

    @property
    def eur_decimal(self) -> Decimal | None:
        return Decimal(self.eur_try) if self.eur_try is not None else None

    def province_snapshot(self, province: str) -> FuelProvinceSnapshot | None:
        p = get_province(province)
        raw = self.fuel_prices.get(p.key)
        if not raw:
            return None
        return FuelProvinceSnapshot(
            province_name=raw.get("province_name") or p.name,
            diesel_price_try_per_liter=raw.get("diesel_price_try_per_liter"),
            gasoline_price_try_per_liter=raw.get("gasoline_price_try_per_liter"),
            source_date=raw.get("source_date"),
            source_name=raw.get("source_name"),
            updated_at=raw.get("updated_at"),
        )

    def price_for(self, fuel_type: str, province: str) -> Decimal | None:
        item = self.province_snapshot(province)
        return item.price_for(fuel_type) if item else None

    def ready_for(self, fuel_type: str, province: str) -> bool:
        return self.eur_decimal is not None and self.price_for(fuel_type, province) is not None


class MarketDataStore:
    """TCMB EUR kuru ile seçilen illerin Petrol Ofisi benzin/motorin fiyatlarını önbellekler."""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self._lock = threading.Lock()
        self._snapshot = self._load_cache()

    def _load_cache(self) -> MarketSnapshot:
        try:
            if self.cache_path.exists():
                raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
                fuel_prices = raw.get("fuel_prices") or {}

                # v3.4 ve öncesi tek-il önbelleğini Samsun kaydına taşı.
                if not fuel_prices and (
                    raw.get("diesel_price_try_per_liter") or raw.get("gasoline_price_try_per_liter")
                ):
                    fuel_prices["samsun"] = {
                        "province_name": "Samsun",
                        "diesel_price_try_per_liter": raw.get("diesel_price_try_per_liter")
                        or raw.get("fuel_price_try_per_liter"),
                        "gasoline_price_try_per_liter": raw.get("gasoline_price_try_per_liter"),
                        "source_date": raw.get("diesel_source_date") or raw.get("gasoline_source_date") or raw.get("fuel_source_date"),
                        "source_name": raw.get("diesel_source_name") or raw.get("gasoline_source_name") or "Eski Samsun önbelleği",
                        "updated_at": raw.get("diesel_updated_at") or raw.get("gasoline_updated_at") or raw.get("fuel_updated_at"),
                    }

                return MarketSnapshot(
                    eur_try=raw.get("eur_try"),
                    eur_source_date=raw.get("eur_source_date"),
                    eur_updated_at=raw.get("eur_updated_at"),
                    fuel_prices=fuel_prices,
                    last_refresh_at=raw.get("last_refresh_at"),
                )
        except Exception as exc:
            logger.warning("Otomatik veri önbelleği okunamadı: %s", exc)
        return MarketSnapshot()

    def _save_cache_locked(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        payload = {
            "eur_try": self._snapshot.eur_try,
            "eur_source_date": self._snapshot.eur_source_date,
            "eur_updated_at": self._snapshot.eur_updated_at,
            "fuel_prices": self._snapshot.fuel_prices,
            "last_refresh_at": self._snapshot.last_refresh_at,
        }
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.cache_path)

    def get(self) -> MarketSnapshot:
        with self._lock:
            # JSON round-trip = nested dict için güvenli kopya.
            return MarketSnapshot(
                eur_try=self._snapshot.eur_try,
                eur_source_date=self._snapshot.eur_source_date,
                eur_updated_at=self._snapshot.eur_updated_at,
                fuel_prices=json.loads(json.dumps(self._snapshot.fuel_prices, ensure_ascii=False)),
                last_refresh_at=self._snapshot.last_refresh_at,
            )

    def refresh(self, provinces: Iterable[str] | None = None) -> dict[str, Any]:
        province_names = []
        for value in provinces or ["Samsun"]:
            try:
                name = get_province(value).name
            except KeyError:
                logger.warning("Bilinmeyen akaryakıt ili atlandı: %s", value)
                continue
            if name not in province_names:
                province_names.append(name)
        if not province_names:
            province_names = ["Samsun"]

        now = datetime.now(TZ).isoformat(timespec="seconds")
        eur_error: str | None = None
        province_errors: dict[str, str] = {}

        try:
            eur_value, eur_date = fetch_tcmb_eur_selling()
            with self._lock:
                self._snapshot.eur_try = str(eur_value)
                self._snapshot.eur_source_date = eur_date
                self._snapshot.eur_updated_at = now
            logger.info("TCMB EUR Döviz Satış güncellendi: %s TL (%s)", eur_value, eur_date)
        except Exception as exc:
            eur_error = str(exc)
            logger.warning("TCMB EUR kuru güncellenemedi; son değer korunuyor: %s", exc)

        for province_name in province_names:
            p = get_province(province_name)
            try:
                gasoline_value, diesel_value = fetch_petrol_ofisi_prices(p.name)
                source_date = datetime.now(TZ).date().isoformat()
                with self._lock:
                    self._snapshot.fuel_prices[p.key] = {
                        "province_name": p.name,
                        "gasoline_price_try_per_liter": str(gasoline_value),
                        "diesel_price_try_per_liter": str(diesel_value),
                        "source_date": source_date,
                        "source_name": f"Petrol Ofisi {p.name}",
                        "updated_at": now,
                    }
                logger.info(
                    "%s Petrol Ofisi fiyatları güncellendi: Benzin=%s TL/L, Motorin=%s TL/L",
                    p.name,
                    gasoline_value,
                    diesel_value,
                )
            except Exception as exc:
                province_errors[p.name] = str(exc)
                logger.warning("%s Petrol Ofisi fiyatları güncellenemedi; son değer korunuyor: %s", p.name, exc)

        with self._lock:
            self._snapshot.last_refresh_at = now
            self._save_cache_locked()
            snapshot = self.get_unlocked_copy()

        return {
            "snapshot": snapshot,
            "eur_ok": eur_error is None,
            "eur_error": eur_error,
            "province_errors": province_errors,
            "fuel_ok": not province_errors,
        }

    def get_unlocked_copy(self) -> MarketSnapshot:
        return MarketSnapshot(
            eur_try=self._snapshot.eur_try,
            eur_source_date=self._snapshot.eur_source_date,
            eur_updated_at=self._snapshot.eur_updated_at,
            fuel_prices=json.loads(json.dumps(self._snapshot.fuel_prices, ensure_ascii=False)),
            last_refresh_at=self._snapshot.last_refresh_at,
        )


def _get(url: str) -> requests.Response:
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def fetch_tcmb_eur_selling() -> tuple[Decimal, str]:
    response = _get(TCMB_URL)
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise RuntimeError("TCMB XML yanıtı çözümlenemedi") from exc

    currency = root.find(".//Currency[@CurrencyCode='EUR']")
    if currency is None:
        raise RuntimeError("TCMB XML içinde EUR bulunamadı")

    raw = (currency.findtext("ForexSelling") or "").strip().replace(",", ".")
    if not raw:
        raise RuntimeError("TCMB EUR Döviz Satış alanı boş")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise RuntimeError(f"TCMB EUR değeri geçersiz: {raw}") from exc
    if value <= 0:
        raise RuntimeError("TCMB EUR değeri sıfır/negatif geldi")

    source_date = (root.attrib.get("Tarih") or root.attrib.get("Date") or datetime.now(TZ).date().isoformat()).strip()
    return value, source_date


def _parse_price(text: str) -> Decimal | None:
    # Petrol Ofisi hücresinde ilk görünen ondalıklı değer KDV dahil fiyattır.
    matches = re.findall(r"(?<!\d)(\d{1,3}[\.,]\d{2})(?!\d)", text)
    for raw in matches:
        try:
            value = Decimal(raw.replace(",", "."))
        except InvalidOperation:
            continue
        if Decimal("20") <= value <= Decimal("200"):
            return value
    return None


def _ascii_tr(value: str) -> str:
    return (
        value.upper()
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ç", "C")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
    )


def fetch_petrol_ofisi_prices(province: str) -> tuple[Decimal, Decimal]:
    """Petrol Ofisi il sayfasından (benzin, motorin) KDV dahil fiyatlarını alır.

    İl merkez satırı varsa onu kullanır. İstanbul gibi merkez adının parantezli
    bölündüğü sayfalarda il adıyla başlayan ilk satır seçilir.
    """
    p = get_province(province)
    po_slug = {"afyonkarahisar": "afyon"}.get(p.key, p.key)
    url = PETROL_OFISI_URL.format(slug=po_slug)
    response = _get(url)
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    gasoline_index: int | None = None
    diesel_index: int | None = None
    data_rows: list[tuple[list[str], list[str]]] = []

    for tr in soup.find_all("tr"):
        cells = [" ".join(cell.stripped_strings) for cell in tr.find_all(["th", "td"])]
        if not cells:
            continue
        normalized = [_ascii_tr(cell).strip() for cell in cells]

        for idx, cell in enumerate(normalized):
            if "KURSUNSUZ 95" in cell or ("BENZIN" in cell and "DIESEL" not in cell):
                gasoline_index = idx
            if "DIESEL" in cell or "MOTORIN" in cell:
                diesel_index = idx

        if any(_parse_price(cell) is not None for cell in cells[1:]):
            data_rows.append((cells, normalized))

    target = {"afyonkarahisar": "AFYON"}.get(p.key, _ascii_tr(p.name).strip())
    candidates = [row for row in data_rows if row[1] and row[1][0] == target]
    if not candidates:
        candidates = [row for row in data_rows if row[1] and row[1][0].startswith(target)]
    if not candidates:
        candidates = data_rows[:1]
    if not candidates:
        raise RuntimeError(f"Petrol Ofisi {p.name} fiyat tablosu bulunamadı")

    cells, _normalized = candidates[0]
    gasoline: Decimal | None = None
    diesel: Decimal | None = None
    for idx in [gasoline_index, 1]:
        if idx is not None and 0 <= idx < len(cells):
            gasoline = _parse_price(cells[idx])
            if gasoline is not None:
                break
    for idx in [diesel_index, 2]:
        if idx is not None and 0 <= idx < len(cells):
            diesel = _parse_price(cells[idx])
            if diesel is not None:
                break

    if gasoline is None or diesel is None:
        raise RuntimeError(f"Petrol Ofisi {p.name} benzin/motorin fiyatları ayrıştırılamadı")
    return gasoline, diesel
