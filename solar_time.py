from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import acos, asin, atan, cos, degrees, radians, sin, tan
from zoneinfo import ZoneInfo

from provinces import get_province

TURKEY_TZ = ZoneInfo("Europe/Istanbul")
OFFICIAL_ZENITH_DEGREES = 90.833


@dataclass(frozen=True)
class DutyLightSplit:
    basis_date: date
    day_minutes: int
    night_minutes: int
    province_name: str = "Samsun"

    @property
    def day_text(self) -> str:
        return format_minutes(self.day_minutes)

    @property
    def night_text(self) -> str:
        return format_minutes(self.night_minutes)


def format_minutes(minutes: int) -> str:
    hours, mins = divmod(max(0, int(minutes)), 60)
    return f"{hours} SA {mins:02d} DA"


def _normalize_degrees(value: float) -> float:
    return value % 360.0


def _normalize_hours(value: float) -> float:
    return value % 24.0


def _solar_event_utc(day: date, *, latitude: float, longitude: float, sunrise: bool) -> datetime:
    n = day.timetuple().tm_yday
    lng_hour = longitude / 15.0
    approx_time = n + (((6.0 if sunrise else 18.0) - lng_hour) / 24.0)

    mean_anomaly = (0.9856 * approx_time) - 3.289
    true_longitude = (
        mean_anomaly
        + (1.916 * sin(radians(mean_anomaly)))
        + (0.020 * sin(radians(2.0 * mean_anomaly)))
        + 282.634
    )
    true_longitude = _normalize_degrees(true_longitude)

    right_ascension = degrees(atan(0.91764 * tan(radians(true_longitude))))
    right_ascension = _normalize_degrees(right_ascension)
    l_quadrant = (int(true_longitude / 90.0)) * 90.0
    ra_quadrant = (int(right_ascension / 90.0)) * 90.0
    right_ascension = (right_ascension + (l_quadrant - ra_quadrant)) / 15.0

    sin_declination = 0.39782 * sin(radians(true_longitude))
    cos_declination = cos(asin(sin_declination))
    cos_hour_angle = (
        cos(radians(OFFICIAL_ZENITH_DEGREES))
        - (sin_declination * sin(radians(latitude)))
    ) / (cos_declination * cos(radians(latitude)))

    if cos_hour_angle > 1.0 or cos_hour_angle < -1.0:
        raise ValueError("Bu tarih/konum için güneş doğuş-batış zamanı hesaplanamadı.")

    hour_angle = 360.0 - degrees(acos(cos_hour_angle)) if sunrise else degrees(acos(cos_hour_angle))
    hour_angle /= 15.0
    local_mean_time = hour_angle + right_ascension - (0.06571 * approx_time) - 6.622
    utc_hour = _normalize_hours(local_mean_time - lng_hour)

    seconds = int(round(utc_hour * 3600.0))
    if seconds >= 86400:
        seconds -= 86400
        day = day + timedelta(days=1)
    return datetime.combine(day, time(0, 0), tzinfo=timezone.utc) + timedelta(seconds=seconds)


def sunrise_sunset(day: date, *, province: str = "Samsun") -> tuple[datetime, datetime]:
    p = get_province(province)
    sunrise_utc = _solar_event_utc(day, latitude=p.latitude, longitude=p.longitude, sunrise=True)
    sunset_utc = _solar_event_utc(day, latitude=p.latitude, longitude=p.longitude, sunrise=False)
    return sunrise_utc.astimezone(TURKEY_TZ), sunset_utc.astimezone(TURKEY_TZ)


def split_duty_by_daylight(
    departure: str,
    arrival: str,
    *,
    basis_date: date,
    province: str = "Samsun",
) -> DutyLightSplit:
    p = get_province(province)
    dep_h, dep_m = [int(x) for x in departure.split(":", 1)]
    arr_h, arr_m = [int(x) for x in arrival.split(":", 1)]

    start = datetime.combine(basis_date, time(dep_h, dep_m), tzinfo=TURKEY_TZ)
    end = datetime.combine(basis_date, time(arr_h, arr_m), tzinfo=TURKEY_TZ)
    if end < start:
        end += timedelta(days=1)

    total_minutes = int((end - start).total_seconds() // 60)
    if total_minutes <= 0:
        return DutyLightSplit(
            basis_date=basis_date,
            day_minutes=0,
            night_minutes=0,
            province_name=p.name,
        )

    daylight_seconds = 0.0
    current_day = start.date()
    final_day = end.date()
    while current_day <= final_day:
        sunrise, sunset = sunrise_sunset(current_day, province=p.key)
        overlap_start = max(start, sunrise)
        overlap_end = min(end, sunset)
        if overlap_end > overlap_start:
            daylight_seconds += (overlap_end - overlap_start).total_seconds()
        current_day += timedelta(days=1)

    day_minutes = int(round(daylight_seconds / 60.0))
    day_minutes = max(0, min(total_minutes, day_minutes))
    night_minutes = total_minutes - day_minutes
    return DutyLightSplit(
        basis_date=basis_date,
        day_minutes=day_minutes,
        night_minutes=night_minutes,
        province_name=p.name,
    )
