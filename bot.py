from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import sqlite3
from contextlib import suppress
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Update, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from calculator import (
    DAILY_AMORTIZATION_EUR,
    DIESEL_DENSITY_KG_PER_L,
    GASOLINE_DENSITY_KG_PER_L,
    calculate,
    format_tr,
    normalize_time,
    parse_decimal,
)
from market_data import MarketDataStore, MarketSnapshot
from provinces import PROVINCES, get_province
from solar_time import DutyLightSplit, split_duty_by_daylight, sunrise_sunset

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Istanbul")
DB_PATH = Path(os.getenv("HISTORY_DB_PATH", "data/history.db"))
MARKET_DATA_PATH = Path(os.getenv("MARKET_DATA_PATH", "data/market_data.json"))
MARKET_STORE = MarketDataStore(MARKET_DATA_PATH)
HISTORY_PAGE_SIZE = 6
AUTO_REFRESH_HOUR = 17
AUTO_REFRESH_MINUTE = 0
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

EXCEL_EXAMPLES: dict[str, Any] = {
    "departure": "09:35",
    "arrival": "19:25",
    "personnel": 4,
    "fuel_liters": Decimal("750"),
    "fuel_type": "diesel",
}

DEFAULT_USER_SETTINGS: dict[str, Any] = {
    "fuel_province": "Samsun",
    "solar_province": "Samsun",
    "monthly_salary": Decimal("105000"),
}
PROVINCE_PAGE_SIZE = 12

FUEL_TYPES = {
    "diesel": {
        "label": "Dizel",
        "price_label": "Motorin",
        "density": DIESEL_DENSITY_KG_PER_L,
    },
    "gasoline": {
        "label": "Benzin",
        "price_label": "Benzin",
        "density": GASOLINE_DENSITY_KG_PER_L,
    },
}

FIELD_LABELS = {
    "departure": "Avara",
    "arrival": "Aborda",
    "personnel": "Personel",
    "fuel_liters": "Yakıt",
}

NUMERIC_FIELDS = {"personnel", "fuel_liters"}
TIME_FIELDS = {"departure", "arrival"}


def parse_authorized_users() -> tuple[bool, set[int]]:
    raw = os.getenv("AUTHORIZED_USER_IDS", "").strip()
    if raw == "*":
        return True, set()
    ids: set[int] = set()
    for item in raw.replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.add(int(item))
        except ValueError as exc:
            raise RuntimeError(f"AUTHORIZED_USER_IDS içinde geçersiz Telegram ID: {item}") from exc
    return False, ids


ALLOW_ALL_USERS, AUTHORIZED_USER_IDS = parse_authorized_users()


def parse_admin_users() -> set[int]:
    """Yönetici ID'lerini oku. ADMIN_USER_IDS boşsa ilk yetkili ID yöneticidir."""
    raw = os.getenv("ADMIN_USER_IDS", "").strip()
    source = raw if raw else os.getenv("AUTHORIZED_USER_IDS", "").strip()
    if not source or source == "*":
        return set()
    ids: list[int] = []
    for item in source.replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError:
            continue
        if not raw:  # Fallback modunda yalnızca ilk yetkili kullanıcı yönetici olsun.
            break
    return set(ids)


ADMIN_USER_IDS = parse_admin_users()


def is_admin_user_id(user_id: int | None) -> bool:
    return bool(user_id is not None and user_id in ADMIN_USER_IDS)


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and is_admin_user_id(user.id))


def is_authorized(update: Update) -> bool:
    user = update.effective_user
    return bool(user and (ALLOW_ALL_USERS or user.id in AUTHORIZED_USER_IDS))


async def deny_access(update: Update) -> None:
    user = update.effective_user
    user_id = user.id if user else "bilinmiyor"
    if user:
        log_activity(update, "Yetkisiz erişim denemesi")
    text = (
        "⛔ <b>Bu botu kullanma yetkiniz yok.</b>\n\n"
        f"Telegram kullanıcı ID'niz: <code>{user_id}</code>\n"
        "Yönetici bu ID'yi <code>AUTHORIZED_USER_IDS</code> listesine eklemelidir."
    )
    if update.callback_query:
        await update.callback_query.answer("Bu işlem için yetkiniz yok.", show_alert=True)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def require_auth(update: Update) -> bool:
    if is_authorized(update):
        return True
    await deny_access(update)
    return False


def db_connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                created_at TEXT NOT NULL,
                departure TEXT NOT NULL,
                arrival TEXT NOT NULL,
                eur_rate TEXT NOT NULL,
                monthly_salary TEXT NOT NULL,
                personnel INTEGER NOT NULL,
                fuel_liters TEXT NOT NULL,
                fuel_type TEXT NOT NULL DEFAULT 'diesel',
                fuel_province TEXT NOT NULL DEFAULT 'Samsun',
                solar_province TEXT NOT NULL DEFAULT 'Samsun',
                fuel_price TEXT NOT NULL,
                duration_text TEXT NOT NULL,
                day_minutes INTEGER,
                night_minutes INTEGER,
                solar_basis_date TEXT,
                amortization_cost TEXT NOT NULL,
                personnel_cost TEXT NOT NULL,
                fuel_cost TEXT NOT NULL,
                total_cost TEXT NOT NULL,
                gorrap_line TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(calculations)").fetchall()}
        if "fuel_type" not in columns:
            conn.execute("ALTER TABLE calculations ADD COLUMN fuel_type TEXT NOT NULL DEFAULT 'diesel'")
        if "fuel_province" not in columns:
            conn.execute("ALTER TABLE calculations ADD COLUMN fuel_province TEXT NOT NULL DEFAULT 'Samsun'")
        if "solar_province" not in columns:
            conn.execute("ALTER TABLE calculations ADD COLUMN solar_province TEXT NOT NULL DEFAULT 'Samsun'")
        if "day_minutes" not in columns:
            conn.execute("ALTER TABLE calculations ADD COLUMN day_minutes INTEGER")
        if "night_minutes" not in columns:
            conn.execute("ALTER TABLE calculations ADD COLUMN night_minutes INTEGER")
        if "solar_basis_date" not in columns:
            conn.execute("ALTER TABLE calculations ADD COLUMN solar_basis_date TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_calculations_user_date ON calculations(user_id, id DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                fuel_province TEXT NOT NULL DEFAULT 'Samsun',
                solar_province TEXT NOT NULL DEFAULT 'Samsun',
                monthly_salary TEXT NOT NULL DEFAULT '105000',
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_log_date ON activity_log(id DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_log_user_date ON activity_log(user_id, id DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_user_labels (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Yönetici paneli ilk kez eklendiğinde mevcut hesaplamaları da işlem günlüğüne taşı.
        conn.execute(
            """
            INSERT INTO activity_log (user_id, username, full_name, action, detail, created_at)
            SELECT
                c.user_id, c.username, c.full_name, 'Hesaplama yaptı',
                'Geçmiş kayıt #' || c.id, c.created_at
            FROM calculations c
            WHERE NOT EXISTS (
                SELECT 1 FROM activity_log a
                WHERE a.action = 'Hesaplama yaptı'
                  AND a.user_id = c.user_id
                  AND a.created_at = c.created_at
            )
            """
        )

        # v3.4'ten yükseltmede son hesaplamadaki maaşı ilk sabit ayar olarak devral.
        now = datetime.now(TZ).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT OR IGNORE INTO user_settings (user_id, fuel_province, solar_province, monthly_salary, updated_at)
            SELECT c.user_id, 'Samsun', 'Samsun', c.monthly_salary, ?
            FROM calculations c
            JOIN (
                SELECT user_id, MAX(id) AS max_id
                FROM calculations
                GROUP BY user_id
            ) latest ON latest.user_id = c.user_id AND latest.max_id = c.id
            """,
            (now,),
        )


def log_activity(update: Update, action: str, detail: str | None = None) -> None:
    user = update.effective_user
    if not user:
        return
    try:
        with db_connect() as conn:
            conn.execute(
                """
                INSERT INTO activity_log (user_id, username, full_name, action, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.username,
                    user.full_name,
                    action,
                    detail,
                    datetime.now(TZ).isoformat(timespec="seconds"),
                ),
            )
    except Exception:
        logger.exception("Kullanıcı işlem günlüğü yazılamadı")


def admin_dashboard_stats() -> dict[str, int]:
    today = datetime.now(TZ).date().isoformat()
    with db_connect() as conn:
        total_calcs = conn.execute("SELECT COUNT(*) FROM calculations").fetchone()[0]
        today_calcs = conn.execute(
            "SELECT COUNT(*) FROM calculations WHERE substr(created_at, 1, 10) = ?", (today,)
        ).fetchone()[0]
        distinct_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM activity_log"
        ).fetchone()[0]
        total_actions = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
    return {
        "total_calcs": int(total_calcs),
        "today_calcs": int(today_calcs),
        "distinct_users": int(distinct_users),
        "total_actions": int(total_actions),
    }


def recent_activity(limit: int = 12) -> list[sqlite3.Row]:
    with db_connect() as conn:
        return conn.execute(
            """
            SELECT a.id, a.user_id, a.username, a.full_name, a.action, a.detail, a.created_at,
                   COALESCE(l.display_name, '') AS custom_name
            FROM activity_log a
            LEFT JOIN admin_user_labels l ON l.user_id = a.user_id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def admin_user_summary(limit: int = 30) -> list[dict[str, Any]]:
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT
                a.user_id,
                COALESCE(MAX(NULLIF(a.username, '')), '') AS username,
                COALESCE(MAX(NULLIF(a.full_name, '')), '') AS full_name,
                COALESCE(MAX(l.display_name), '') AS custom_name,
                COUNT(*) AS action_count,
                SUM(CASE WHEN a.action = 'Hesaplama yaptı' THEN 1 ELSE 0 END) AS calculation_count,
                MAX(a.created_at) AS last_seen,
                MAX(a.id) AS last_id
            FROM activity_log a
            LEFT JOIN admin_user_labels l ON l.user_id = a.user_id
            GROUP BY a.user_id
            ORDER BY MAX(a.id) DESC
            """
        ).fetchall()
        result = [dict(row) for row in rows]
        known_ids = {int(row["user_id"]) for row in result}
        configured_ids = set(AUTHORIZED_USER_IDS) | set(ADMIN_USER_IDS)
        for user_id in sorted(configured_ids):
            if user_id in known_ids:
                continue
            label_row = conn.execute(
                "SELECT display_name FROM admin_user_labels WHERE user_id = ?", (user_id,)
            ).fetchone()
            result.append(
                {
                    "user_id": user_id,
                    "username": "",
                    "full_name": "",
                    "custom_name": str(label_row["display_name"]) if label_row else "",
                    "action_count": 0,
                    "calculation_count": 0,
                    "last_seen": None,
                    "last_id": -1,
                }
            )
    return result[:limit]


def admin_user_detail(user_id: int) -> dict[str, Any] | None:
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT
                a.user_id,
                COALESCE(MAX(NULLIF(a.username, '')), '') AS username,
                COALESCE(MAX(NULLIF(a.full_name, '')), '') AS full_name,
                COALESCE(MAX(l.display_name), '') AS custom_name,
                COUNT(*) AS action_count,
                SUM(CASE WHEN a.action = 'Hesaplama yaptı' THEN 1 ELSE 0 END) AS calculation_count,
                MIN(a.created_at) AS first_seen,
                MAX(a.created_at) AS last_seen
            FROM activity_log a
            LEFT JOIN admin_user_labels l ON l.user_id = a.user_id
            WHERE a.user_id = ?
            GROUP BY a.user_id
            """,
            (user_id,),
        ).fetchone()
        if row:
            return dict(row)
        label_row = conn.execute(
            "SELECT display_name FROM admin_user_labels WHERE user_id = ?", (user_id,)
        ).fetchone()
        if user_id in AUTHORIZED_USER_IDS or user_id in ADMIN_USER_IDS or label_row:
            return {
                "user_id": user_id,
                "username": "",
                "full_name": "",
                "custom_name": str(label_row["display_name"]) if label_row else "",
                "action_count": 0,
                "calculation_count": 0,
                "first_seen": None,
                "last_seen": None,
            }
    return None


def set_admin_user_label(user_id: int, display_name: str) -> None:
    name = display_name.strip()
    if not name:
        raise ValueError("İsim boş olamaz")
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO admin_user_labels (user_id, display_name, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                updated_at = excluded.updated_at
            """,
            (user_id, name, datetime.now(TZ).isoformat(timespec="seconds")),
        )


def delete_admin_user_label(user_id: int) -> None:
    with db_connect() as conn:
        conn.execute("DELETE FROM admin_user_labels WHERE user_id = ?", (user_id,))


def _admin_identity(row: Any, *, show_id: bool = True) -> str:
    custom_name = str(row["custom_name"] or "").strip() if "custom_name" in row.keys() else ""
    username = str(row["username"] or "").strip() if "username" in row.keys() else ""
    full_name = str(row["full_name"] or "").strip() if "full_name" in row.keys() else ""
    user_id = int(row["user_id"])
    if custom_name:
        base = f"<b>{html.escape(custom_name)}</b>"
    elif username:
        base = f"@{html.escape(username)}"
    elif full_name:
        base = html.escape(full_name)
    else:
        base = f"Kullanıcı {user_id}"
    if show_id:
        base += f" • <code>{user_id}</code>"
    return base


def _admin_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return value


def save_history(update: Update, data: dict[str, Any], result: Any, light_split: DutyLightSplit) -> int:
    user = update.effective_user
    if not user:
        raise RuntimeError("Kullanıcı bilgisi alınamadı.")
    created_at = datetime.now(TZ).isoformat(timespec="seconds")
    with db_connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO calculations (
                user_id, username, full_name, created_at,
                departure, arrival, eur_rate, monthly_salary, personnel,
                fuel_liters, fuel_type, fuel_province, solar_province, fuel_price, duration_text,
                day_minutes, night_minutes, solar_basis_date,
                amortization_cost, personnel_cost, fuel_cost, total_cost, gorrap_line
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.username,
                user.full_name,
                created_at,
                result.departure,
                result.arrival,
                str(data["eur_rate"]),
                str(data["monthly_salary"]),
                int(data["personnel"]),
                str(data["fuel_liters"]),
                str(data.get("fuel_type", "diesel")),
                str(data.get("fuel_province", "Samsun")),
                str(data.get("solar_province", "Samsun")),
                str(data["fuel_price"]),
                result.duration_text,
                int(light_split.day_minutes),
                int(light_split.night_minutes),
                light_split.basis_date.isoformat(),
                str(result.amortization_cost_try),
                str(result.personnel_cost_try),
                str(result.fuel_cost_try),
                str(result.total_cost_try),
                result.gorrap_line,
            ),
        )
        return int(cursor.lastrowid)


def history_count(user_id: int) -> int:
    with db_connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM calculations WHERE user_id = ?", (user_id,)).fetchone()[0])


def history_page(user_id: int, page: int) -> list[sqlite3.Row]:
    offset = max(page, 0) * HISTORY_PAGE_SIZE
    with db_connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM calculations WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (user_id, HISTORY_PAGE_SIZE, offset),
            ).fetchall()
        )


def history_item(user_id: int, item_id: int) -> sqlite3.Row | None:
    with db_connect() as conn:
        return conn.execute(
            "SELECT * FROM calculations WHERE user_id = ? AND id = ?",
            (user_id, item_id),
        ).fetchone()


def latest_inputs(user_id: int) -> dict[str, Any] | None:
    with db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM calculations WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "departure": row["departure"],
        "arrival": row["arrival"],
        "personnel": int(row["personnel"]),
        "fuel_liters": Decimal(row["fuel_liters"]),
        "fuel_type": row["fuel_type"] if row["fuel_type"] in FUEL_TYPES else "diesel",
    }


def clear_history(user_id: int) -> None:
    with db_connect() as conn:
        conn.execute("DELETE FROM calculations WHERE user_id = ?", (user_id,))


def get_user_settings(user_id: int) -> dict[str, Any]:
    with db_connect() as conn:
        row = conn.execute(
            "SELECT fuel_province, solar_province, monthly_salary FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return dict(DEFAULT_USER_SETTINGS)
    settings = {
        "fuel_province": row["fuel_province"],
        "solar_province": row["solar_province"],
        "monthly_salary": Decimal(row["monthly_salary"]),
    }
    for key in ("fuel_province", "solar_province"):
        try:
            settings[key] = get_province(str(settings[key])).name
        except KeyError:
            settings[key] = "Samsun"
    return settings


def save_user_setting(user_id: int, key: str, value: Any) -> None:
    if key not in {"fuel_province", "solar_province", "monthly_salary"}:
        raise ValueError("Geçersiz kullanıcı ayarı")
    current = get_user_settings(user_id)
    current[key] = value
    now = datetime.now(TZ).isoformat(timespec="seconds")
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, fuel_province, solar_province, monthly_salary, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                fuel_province=excluded.fuel_province,
                solar_province=excluded.solar_province,
                monthly_salary=excluded.monthly_salary,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                str(current["fuel_province"]),
                str(current["solar_province"]),
                str(current["monthly_salary"]),
                now,
            ),
        )


def configured_fuel_provinces() -> list[str]:
    with db_connect() as conn:
        rows = conn.execute("SELECT DISTINCT fuel_province FROM user_settings").fetchall()
    values = [str(row[0]) for row in rows if row[0]]
    return values or ["Samsun"]


def fresh_calc_data() -> dict[str, Any]:
    return dict(EXCEL_EXAMPLES)


def get_calc_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    data = context.user_data.get("calc")
    if not isinstance(data, dict):
        data = fresh_calc_data()
        context.user_data["calc"] = data
    return data


def money(value: Any) -> str:
    return format_tr(value)


def main_menu_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.extend([
        [InlineKeyboardButton("🧮 Yeni hesaplama", callback_data="nav:new")],
        [InlineKeyboardButton("📚 Geçmiş hesaplamalar", callback_data="nav:history:0")],
        [InlineKeyboardButton("⚙️ Sabit Ayarlar", callback_data="nav:settings")],
        [InlineKeyboardButton("📡 Otomatik veriler", callback_data="nav:data")],
        [InlineKeyboardButton("📌 Excel sabitleri", callback_data="nav:constants")],
    ])
    if is_admin_user_id(user_id):
        rows.append([InlineKeyboardButton("👑 Yönetici Paneli", callback_data="admin:panel")])
    return InlineKeyboardMarkup(rows)


def _source_date_text(value: str | None) -> str:
    if not value:
        return "—"
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except Exception:
        pass
    return value


def fuel_type_label(fuel_type: str) -> str:
    return FUEL_TYPES.get(fuel_type, FUEL_TYPES["diesel"])["label"]


def fuel_density(fuel_type: str) -> Decimal:
    return FUEL_TYPES.get(fuel_type, FUEL_TYPES["diesel"])["density"]


def auto_values_text(
    user_id: int,
    snapshot: MarketSnapshot | None = None,
    selected_fuel_type: str | None = None,
) -> str:
    settings = get_user_settings(user_id)
    fuel_province = settings["fuel_province"]
    snap = snapshot or MARKET_STORE.get()
    eur = f"₺{money(snap.eur_decimal)}" if snap.eur_decimal is not None else "⚠️ alınamadı"
    fuel = snap.province_snapshot(fuel_province)
    diesel = f"₺{money(fuel.diesel_decimal)}/L" if fuel and fuel.diesel_decimal is not None else "⚠️ alınamadı"
    gasoline = f"₺{money(fuel.gasoline_decimal)}/L" if fuel and fuel.gasoline_decimal is not None else "⚠️ alınamadı"
    source_date = _source_date_text(fuel.source_date if fuel else None)
    diesel_mark = " ✅" if selected_fuel_type == "diesel" else ""
    gasoline_mark = " ✅" if selected_fuel_type == "gasoline" else ""
    return (
        f"💶 <b>Euro:</b> {eur} <i>(TCMB Döviz Satış • {_source_date_text(snap.eur_source_date)})</i>\n"
        f"⛽ <b>{html.escape(fuel_province)} motorin:</b> {diesel}{diesel_mark} <i>(Petrol Ofisi • {source_date})</i>\n"
        f"⛽ <b>{html.escape(fuel_province)} benzin:</b> {gasoline}{gasoline_mark} <i>(Petrol Ofisi • {source_date})</i>"
    )

def calc_panel_text(data: dict[str, Any]) -> str:
    selected = data.get("fuel_type", "diesel")
    return (
        "<b>🧮 GÖREV MALİYET HESAPLAMA</b>\n"
        "Sık kullanılan değerleri burada ayarlayın. Maaş ve il seçimleri <b>Sabit Ayarlar</b> menüsünde saklanır.\n\n"
        f"🕒 <b>Avara:</b> <code>{html.escape(str(data['departure']))}</code>\n"
        f"⚓ <b>Aborda:</b> <code>{html.escape(str(data['arrival']))}</code>\n"
        f"👥 <b>Personel:</b> {int(data['personnel'])}\n"
        f"⛽ <b>Yakıt:</b> {money(data['fuel_liters'])} L\n"
        f"🛢 <b>Yakıt türü:</b> {fuel_type_label(selected)}\n\n"
        "Tüm değerler doğruysa <b>HESAPLA</b> butonuna basın."
    )

def calc_panel_keyboard(data: dict[str, Any]) -> InlineKeyboardMarkup:
    selected = data.get("fuel_type", "diesel")
    diesel_text = "✅ Dizel" if selected == "diesel" else "Dizel"
    gasoline_text = "✅ Benzin" if selected == "gasoline" else "Benzin"
    rows = [
        [
            InlineKeyboardButton(f"🕒 Avara {data['departure']}", callback_data="edit:departure"),
            InlineKeyboardButton(f"⚓ Aborda {data['arrival']}", callback_data="edit:arrival"),
        ],
        [
            InlineKeyboardButton(f"👥 Personel {int(data['personnel'])}", callback_data="edit:personnel"),
            InlineKeyboardButton(f"⛽ Yakıt {money(data['fuel_liters'])} L", callback_data="edit:fuel_liters"),
        ],
        [
            InlineKeyboardButton(diesel_text, callback_data="fuel:diesel"),
            InlineKeyboardButton(gasoline_text, callback_data="fuel:gasoline"),
        ],
        [InlineKeyboardButton("✅ HESAPLA", callback_data="calc:run")],
    ]
    rows.extend([
        [InlineKeyboardButton("⚙️ Sabit Ayarlar", callback_data="nav:settings")],
        [
            InlineKeyboardButton("↩️ Son değerleri yükle", callback_data="calc:last"),
            InlineKeyboardButton("🧪 Örnek değerler", callback_data="calc:example"),
        ],
        [InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")],
    ])
    return InlineKeyboardMarkup(rows)

def parse_hhmm(value: str) -> tuple[int, int]:
    normalized = normalize_time(value)
    h, m = normalized.split(":")
    return int(h), int(m)


def add_minutes(value: str, delta: int) -> str:
    h, m = parse_hhmm(value)
    total = (h * 60 + m + delta) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def time_editor_text(field: str, value: str) -> str:
    return (
        f"<b>🕒 {FIELD_LABELS[field]} saatini düzenle</b>\n\n"
        f"Seçili saat: <code>{html.escape(value)}</code>\n\n"
        "Dakika/saat butonlarıyla ayarlayın veya doğrudan saat/dakika seçin."
    )


def time_editor_keyboard(field: str, value: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("−1 saat", callback_data=f"time:{field}:delta:-60"),
                InlineKeyboardButton("−10 dk", callback_data=f"time:{field}:delta:-10"),
                InlineKeyboardButton("−1 dk", callback_data=f"time:{field}:delta:-1"),
            ],
            [
                InlineKeyboardButton("+1 dk", callback_data=f"time:{field}:delta:1"),
                InlineKeyboardButton("+10 dk", callback_data=f"time:{field}:delta:10"),
                InlineKeyboardButton("+1 saat", callback_data=f"time:{field}:delta:60"),
            ],
            [
                InlineKeyboardButton("🕐 Saati seç", callback_data=f"time:{field}:hours"),
                InlineKeyboardButton("⏱ Dakikayı seç", callback_data=f"time:{field}:minutes"),
            ],
            [InlineKeyboardButton("✅ Tamam", callback_data="back:calc")],
        ]
    )


def hour_picker_keyboard(field: str, current: str) -> InlineKeyboardMarkup:
    current_hour, _ = parse_hhmm(current)
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(0, 24, 4):
        row = []
        for hour in range(start, start + 4):
            marker = "✓ " if hour == current_hour else ""
            row.append(InlineKeyboardButton(f"{marker}{hour:02d}", callback_data=f"time:{field}:seth:{hour}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("↩️ Geri", callback_data=f"edit:{field}")])
    return InlineKeyboardMarkup(rows)


def minute_picker_keyboard(field: str, current: str) -> InlineKeyboardMarkup:
    _, current_minute = parse_hhmm(current)
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(0, 60, 5):
        row = []
        for minute in range(start, start + 5):
            marker = "✓ " if minute == current_minute else ""
            row.append(InlineKeyboardButton(f"{marker}{minute:02d}", callback_data=f"time:{field}:setm:{minute}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("↩️ Geri", callback_data=f"edit:{field}")])
    return InlineKeyboardMarkup(rows)


def numeric_editor_text(field: str, value: Any) -> str:
    suffix = {
        "personnel": " kişi",
        "fuel_liters": " L",
    }[field]
    shown = str(int(value)) if field == "personnel" else money(value)
    return (
        f"<b>✏️ {FIELD_LABELS[field]} düzenle</b>\n\n"
        f"Seçili değer: <b>{shown}{suffix}</b>\n\n"
        "Butonlarla artırıp azaltabilir veya <b>Özel değer gir</b> seçeneğini kullanabilirsiniz."
    )


def numeric_editor_keyboard(field: str) -> InlineKeyboardMarkup:
    if field == "personnel":
        deltas = [("−1", "-1"), ("+1", "1")]
        presets = [(str(i), str(i)) for i in range(1, 7)]
    elif field == "fuel_liters":
        deltas = [("−100", "-100"), ("−10", "-10"), ("+10", "10"), ("+100", "100")]
        presets = []
    else:
        raise ValueError(f"Düzenlenemeyen alan: {field}")

    rows: list[list[InlineKeyboardButton]] = []
    if len(deltas) == 4:
        rows.append([InlineKeyboardButton(label, callback_data=f"num:{field}:delta:{delta}") for label, delta in deltas[:2]])
        rows.append([InlineKeyboardButton(label, callback_data=f"num:{field}:delta:{delta}") for label, delta in deltas[2:]])
    else:
        rows.append([InlineKeyboardButton(label, callback_data=f"num:{field}:delta:{delta}") for label, delta in deltas])

    if presets:
        rows.append([InlineKeyboardButton(label, callback_data=f"num:{field}:set:{value}") for label, value in presets[:3]])
        rows.append([InlineKeyboardButton(label, callback_data=f"num:{field}:set:{value}") for label, value in presets[3:]])

    rows.append([InlineKeyboardButton("⌨️ Özel değer gir", callback_data=f"num:{field}:custom")])
    rows.append([InlineKeyboardButton("✅ Tamam", callback_data="back:calc")])
    return InlineKeyboardMarkup(rows)


async def safe_edit(query: Any, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    context.user_data.pop("awaiting_field", None)
    context.user_data.pop("awaiting_setting", None)
    text = (
        "<b>⚓ GÖREV SÜRESİ VE MALİYET</b>\n\n"
        "Günlük hesaplamada yalnızca sık değişen değerleri girersiniz. "
        "Akaryakıt ili, gün doğumu/batımı ili ve personel maaşı <b>Sabit Ayarlar</b> menüsünde bir kez seçilir ve hatırlanır."
    )
    user_id = update.effective_user.id if update.effective_user else None
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, text, main_menu_keyboard(user_id))
    else:
        if WEBAPP_URL:
            reply_markup = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Mini App Aç", web_app=WebAppInfo(url=WEBAPP_URL))]],
                resize_keyboard=True
            )
            await update.effective_message.reply_text(
                "<i>İpucu: Ekranın altındaki klavye butonundan Mini App'i hızlıca açabilirsiniz.</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard(user_id))


async def show_identity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.effective_message:
        return
    status = "✅ Yetkili" if is_authorized(update) else "⛔ Yetkisiz"
    await update.effective_message.reply_text(
        f"<b>Telegram kullanıcı ID:</b> <code>{user.id}</code>\n<b>Durum:</b> {status}",
        parse_mode=ParseMode.HTML,
    )


async def start_new_calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    log_activity(update, "Yeni hesaplama açtı")
    context.user_data["calc"] = fresh_calc_data()
    context.user_data.pop("awaiting_field", None)
    context.user_data.pop("awaiting_setting", None)
    data = get_calc_data(context)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, calc_panel_text(data), calc_panel_keyboard(data))
    else:
        await update.effective_message.reply_text(
            calc_panel_text(data), parse_mode=ParseMode.HTML, reply_markup=calc_panel_keyboard(data)
        )


async def show_calc_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = get_calc_data(context)
    context.user_data.pop("awaiting_field", None)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, calc_panel_text(data), calc_panel_keyboard(data))
    else:
        await update.effective_message.reply_text(
            calc_panel_text(data), parse_mode=ParseMode.HTML, reply_markup=calc_panel_keyboard(data)
        )


def settings_screen_text(user_id: int) -> str:
    settings = get_user_settings(user_id)
    return (
        "<b>⚙️ SABİT AYARLAR</b>\n\n"
        "Bu değerleri bir kez seçmeniz yeterlidir. Bot sonraki hesaplamalarda hatırlar.\n\n"
        f"⛽ <b>Akaryakıt fiyat ili:</b> {html.escape(settings['fuel_province'])}\n"
        f"🌅 <b>Gün doğumu/batımı ili:</b> {html.escape(settings['solar_province'])}\n"
        f"💼 <b>Aylık personel maaşı:</b> ₺{money(settings['monthly_salary'])}\n\n"
        "Bu ayarlar hesaplama ekranında gösterilmez; hesap yapılırken arka planda otomatik uygulanır."
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⛽ Akaryakıt ilini seç", callback_data="settings:prov:fuel:0")],
            [InlineKeyboardButton("🌅 Güneş ilini seç", callback_data="settings:prov:solar:0")],
            [InlineKeyboardButton("💼 Personel maaşını ayarla", callback_data="settings:salary")],
            [InlineKeyboardButton("📡 Otomatik veriler", callback_data="nav:data")],
            [InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")],
        ]
    )


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    user = update.effective_user
    if not user:
        return
    context.user_data.pop("awaiting_setting", None)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, settings_screen_text(user.id), settings_keyboard())
    else:
        await update.effective_message.reply_text(
            settings_screen_text(user.id), parse_mode=ParseMode.HTML, reply_markup=settings_keyboard()
        )


def province_picker_keyboard(kind: str, current_province: str, page: int) -> InlineKeyboardMarkup:
    page_count = max(1, (len(PROVINCES) + PROVINCE_PAGE_SIZE - 1) // PROVINCE_PAGE_SIZE)
    page = max(0, min(page, page_count - 1))
    start = page * PROVINCE_PAGE_SIZE
    items = PROVINCES[start : start + PROVINCE_PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(items), 2):
        row: list[InlineKeyboardButton] = []
        for province in items[i : i + 2]:
            marker = "✅ " if province.name == current_province else ""
            row.append(InlineKeyboardButton(
                f"{marker}{province.name}", callback_data=f"settings:setprov:{kind}:{province.key}"
            ))
        rows.append(row)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"settings:prov:{kind}:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{page_count}", callback_data="settings:noop"))
    if page < page_count - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"settings:prov:{kind}:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("↩️ Sabit Ayarlar", callback_data="nav:settings")])
    return InlineKeyboardMarkup(rows)


async def show_province_picker(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, page: int) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user or kind not in {"fuel", "solar"}:
        return
    settings = get_user_settings(user.id)
    current = settings["fuel_province" if kind == "fuel" else "solar_province"]
    title = "Akaryakıt fiyat ili" if kind == "fuel" else "Gün doğumu/batımı ili"
    await query.answer()
    await safe_edit(
        query,
        f"<b>📍 {title} seç</b>\n\nMevcut seçim: <b>{html.escape(current)}</b>\n\nİlinizi seçin:",
        province_picker_keyboard(kind, current, page),
    )


async def set_province_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, province_key: str) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user or kind not in {"fuel", "solar"}:
        return
    try:
        province = get_province(province_key)
    except KeyError:
        await query.answer("Geçersiz il.", show_alert=True)
        return
    key = "fuel_province" if kind == "fuel" else "solar_province"
    save_user_setting(user.id, key, province.name)
    log_activity(update, "Sabit ayar değiştirdi", f"{('Akaryakıt ili' if kind == 'fuel' else 'Güneş ili')}: {province.name}")
    if kind == "fuel":
        await query.answer(f"Akaryakıt ili: {province.name}. Fiyatlar yenileniyor…")
        try:
            await asyncio.to_thread(MARKET_STORE.refresh, [province.name])
        except Exception:
            logger.exception("İl değişiminden sonra akaryakıt verisi yenilenemedi")
    else:
        await query.answer(f"Güneş ili: {province.name}")
    await safe_edit(query, settings_screen_text(user.id), settings_keyboard())


def salary_settings_text(user_id: int) -> str:
    salary = get_user_settings(user_id)["monthly_salary"]
    return (
        "<b>💼 AYLIK PERSONEL MAAŞI</b>\n\n"
        f"Seçili maaş: <b>₺{money(salary)}</b>\n\n"
        "Bu değer yeni hesaplamalarda otomatik kullanılacak ve siz değiştirene kadar hatırlanacaktır."
    )


def salary_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("−10.000", callback_data="settings:salary:delta:-10000"),
                InlineKeyboardButton("−1.000", callback_data="settings:salary:delta:-1000"),
            ],
            [
                InlineKeyboardButton("+1.000", callback_data="settings:salary:delta:1000"),
                InlineKeyboardButton("+10.000", callback_data="settings:salary:delta:10000"),
            ],
            [InlineKeyboardButton("⌨️ Özel maaş gir", callback_data="settings:salary:custom")],
            [InlineKeyboardButton("↩️ Sabit Ayarlar", callback_data="nav:settings")],
        ]
    )


async def show_salary_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    context.user_data.pop("awaiting_setting", None)
    await query.answer()
    await safe_edit(query, salary_settings_text(user.id), salary_settings_keyboard())


async def handle_salary_setting_action(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    settings = get_user_settings(user.id)
    if len(parts) == 4 and parts[2] == "delta":
        salary = max(Decimal("0"), parse_decimal(settings["monthly_salary"]) + Decimal(parts[3]))
        save_user_setting(user.id, "monthly_salary", salary)
        log_activity(update, "Sabit ayar değiştirdi", f"Personel maaşı: ₺{money(salary)}")
        await query.answer("Maaş güncellendi.")
        await safe_edit(query, salary_settings_text(user.id), salary_settings_keyboard())
    elif len(parts) == 3 and parts[2] == "custom":
        context.user_data["awaiting_setting"] = "monthly_salary"
        context.user_data["editor_message_id"] = query.message.message_id if query.message else None
        await query.answer()
        await safe_edit(
            query,
            "<b>⌨️ Aylık personel maaşı</b>\n\nYeni aylık maaşı tek mesaj olarak gönderin.\n<code>Örnek: 105000</code>",
            InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Vazgeç", callback_data="settings:salary")]]),
        )


async def show_constants(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    text = (
        "<b>📌 Excel sabitleri</b>\n\n"
        f"• Günlük amortisman: <b>€{format_tr(DAILY_AMORTIZATION_EUR)}</b>\n"
        f"• Saatlik amortisman: <b>€{format_tr(DAILY_AMORTIZATION_EUR / Decimal(24))}</b>\n"
        f"• Dizel dönüşümü: <b>1 L = {format_tr(DIESEL_DENSITY_KG_PER_L, 3)} kg</b>\n"
        f"• Benzin dönüşümü: <b>1 L = {format_tr(GASOLINE_DENSITY_KG_PER_L, 3)} kg</b>\n"
        "• Saatlik maaş: <b>Aylık maaş / 720</b>\n"
        "• Gece yarısı geçişi: <b>MOD(Aborda − Avara, 1)</b> mantığı\n\n"
        "<b>Otomatik veriler</b>\n"
        "• Euro: <b>TCMB EUR Döviz Satış</b>\n"
        "• Akaryakıt: <b>Sabit Ayarlar'da seçilen ilin Petrol Ofisi V/Max fiyatları</b>\n"
        "• Gece/gündüz: <b>Sabit Ayarlar'da seçilen ilin gün doğumu/batımı</b>\n"
        "• Otomatik piyasa yenilemesi: <b>Her gün 17:00 (Türkiye saati)</b> + bot açılışı"
    )
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚙️ Sabit Ayarlar", callback_data="nav:settings")],
            [InlineKeyboardButton("📡 Otomatik veriler", callback_data="nav:data")],
            [InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")],
        ]
    )
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, text, markup)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


def automatic_data_screen_text(user_id: int) -> str:
    settings = get_user_settings(user_id)
    snap = MARKET_STORE.get()
    fuel_province = settings["fuel_province"]
    fuel = snap.province_snapshot(fuel_province)
    ready = snap.eur_decimal is not None and fuel is not None and fuel.diesel_decimal is not None and fuel.gasoline_decimal is not None
    status = "✅ Hesaplamaya hazır" if ready else "⚠️ Veri eksik — yenilemeyi deneyin"
    last = format_history_date(snap.last_refresh_at) if snap.last_refresh_at else "Henüz yok"
    try:
        sunrise, sunset = sunrise_sunset(datetime.now(TZ).date(), province=settings["solar_province"])
        solar_text = f"🌅 <b>{html.escape(settings['solar_province'])} bugün:</b> {sunrise:%H:%M} doğuş / {sunset:%H:%M} batış"
    except Exception:
        solar_text = f"🌅 <b>Güneş ili:</b> {html.escape(settings['solar_province'])}"
    return (
        "<b>📡 OTOMATİK VERİLER</b>\n\n"
        f"{auto_values_text(user_id, snap)}\n"
        f"{solar_text}\n\n"
        f"<b>Durum:</b> {status}\n"
        f"<b>Son kontrol:</b> {html.escape(last)}\n\n"
        "İl ve maaş tercihleri <b>Sabit Ayarlar</b> menüsünde saklanır. Euro ve seçili ilin Petrol Ofisi fiyatları kullanıcı tarafından elle değiştirilmez."
    )


def automatic_data_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Şimdi yenile", callback_data="data:refresh")],
            [InlineKeyboardButton("⚙️ Sabit Ayarlar", callback_data="nav:settings")],
            [InlineKeyboardButton("🧮 Hesaplamaya dön", callback_data="back:calc")],
            [InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")],
        ]
    )


async def show_automatic_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    user = update.effective_user
    if not user:
        return
    log_activity(update, "Otomatik verileri görüntüledi")
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, automatic_data_screen_text(user.id), automatic_data_keyboard())
    else:
        await update.effective_message.reply_text(
            automatic_data_screen_text(user.id), parse_mode=ParseMode.HTML, reply_markup=automatic_data_keyboard()
        )


async def refresh_automatic_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    province = get_user_settings(user.id)["fuel_province"]
    await query.answer("Veriler kontrol ediliyor…")
    result = await asyncio.to_thread(MARKET_STORE.refresh, [province])
    snap = result["snapshot"]
    if snap.ready_for("diesel", province) and snap.ready_for("gasoline", province):
        message = "✅ Otomatik veriler güncellendi." if result["eur_ok"] and result["fuel_ok"] else "⚠️ Yeni veri alınamadı; varsa son başarılı değer korundu."
    else:
        message = "⚠️ Otomatik veriler henüz tamamlanamadı."
    log_activity(update, "Otomatik verileri yeniledi", province)
    await safe_edit(
        query, automatic_data_screen_text(user.id) + f"\n\n<b>{message}</b>", automatic_data_keyboard()
    )


async def set_fuel_type(update: Update, context: ContextTypes.DEFAULT_TYPE, fuel_type: str) -> None:
    query = update.callback_query
    if not query or fuel_type not in FUEL_TYPES:
        return
    data = get_calc_data(context)
    data["fuel_type"] = fuel_type
    await query.answer(f"Yakıt türü: {fuel_type_label(fuel_type)}")
    await safe_edit(query, calc_panel_text(data), calc_panel_keyboard(data))


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE, field: str) -> None:
    if field not in FIELD_LABELS:
        return
    query = update.callback_query
    if not query:
        return
    data = get_calc_data(context)
    await query.answer()
    if field in TIME_FIELDS:
        await safe_edit(query, time_editor_text(field, str(data[field])), time_editor_keyboard(field, str(data[field])))
    elif field in NUMERIC_FIELDS:
        await safe_edit(query, numeric_editor_text(field, data[field]), numeric_editor_keyboard(field))


async def handle_time_action(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    query = update.callback_query
    if not query or len(parts) < 3:
        return
    field, action = parts[1], parts[2]
    if field not in TIME_FIELDS:
        return
    data = get_calc_data(context)
    current = str(data[field])
    await query.answer()

    if action == "delta" and len(parts) == 4:
        data[field] = add_minutes(current, int(parts[3]))
        await safe_edit(query, time_editor_text(field, data[field]), time_editor_keyboard(field, data[field]))
    elif action == "hours":
        await safe_edit(query, f"<b>🕐 {FIELD_LABELS[field]} — Saat seç</b>\n\nMevcut: <code>{current}</code>", hour_picker_keyboard(field, current))
    elif action == "minutes":
        await safe_edit(query, f"<b>⏱ {FIELD_LABELS[field]} — Dakika seç</b>\n\nMevcut: <code>{current}</code>", minute_picker_keyboard(field, current))
    elif action == "seth" and len(parts) == 4:
        _, minute = parse_hhmm(current)
        data[field] = f"{int(parts[3]):02d}:{minute:02d}"
        await safe_edit(query, time_editor_text(field, data[field]), time_editor_keyboard(field, data[field]))
    elif action == "setm" and len(parts) == 4:
        hour, _ = parse_hhmm(current)
        data[field] = f"{hour:02d}:{int(parts[3]):02d}"
        await safe_edit(query, time_editor_text(field, data[field]), time_editor_keyboard(field, data[field]))


async def handle_numeric_action(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    query = update.callback_query
    if not query or len(parts) < 3:
        return
    field, action = parts[1], parts[2]
    if field not in NUMERIC_FIELDS:
        return
    data = get_calc_data(context)
    await query.answer()

    if action == "delta" and len(parts) == 4:
        delta = Decimal(parts[3])
        if field == "personnel":
            data[field] = max(0, int(data[field]) + int(delta))
        else:
            data[field] = max(Decimal("0"), parse_decimal(data[field]) + delta)
        await safe_edit(query, numeric_editor_text(field, data[field]), numeric_editor_keyboard(field))
    elif action == "set" and len(parts) == 4:
        data[field] = int(parts[3]) if field == "personnel" else Decimal(parts[3])
        await safe_edit(query, numeric_editor_text(field, data[field]), numeric_editor_keyboard(field))
    elif action == "custom":
        context.user_data["awaiting_field"] = field
        context.user_data["editor_message_id"] = query.message.message_id if query.message else None
        unit_hint = {
            "personnel": "Örnek: 4",
            "fuel_liters": "Örnek: 750",
        }[field]
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Vazgeç", callback_data=f"edit:{field}")]])
        await safe_edit(
            query,
            f"<b>⌨️ {FIELD_LABELS[field]} — özel değer</b>\n\n"
            f"Yeni değeri tek mesaj olarak gönderin.\n<code>{unit_hint}</code>",
            markup,
        )


async def custom_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    if not update.message:
        return

    admin_name_user_id = context.user_data.get("awaiting_admin_name_user_id")
    if admin_name_user_id is not None:
        if not is_admin(update):
            context.user_data.pop("awaiting_admin_name_user_id", None)
            await update.message.reply_text("⛔ Bu işlem yalnızca yöneticiye açıktır.")
            return
        name = (update.message.text or "").strip()
        if not name or len(name) > 40:
            await update.message.reply_text("⚠️ 1–40 karakter arasında bir isim girin.")
            return
        target_user_id = int(admin_name_user_id)
        set_admin_user_label(target_user_id, name)
        log_activity(update, "Yönetim ayarı güncellendi", f"Kullanıcı {target_user_id}: {name}")
        context.user_data.pop("awaiting_admin_name_user_id", None)
        message_id = context.user_data.pop("editor_message_id", None)
        try:
            await update.message.delete()
        except Exception:
            pass
        text = admin_user_detail_text(target_user_id)
        markup = admin_user_detail_keyboard(target_user_id)
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=message_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup,
                )
                return
            except Exception as exc:
                logger.debug("Yönetici kullanıcı adı mesajı düzenlenemedi: %s", exc)
        await update.effective_chat.send_message(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        return

    awaiting_setting = context.user_data.get("awaiting_setting")
    if awaiting_setting == "monthly_salary":
        user = update.effective_user
        if not user:
            return
        try:
            value = parse_decimal(update.message.text or "")
            if value < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Geçerli ve negatif olmayan bir maaş girin.")
            return
        save_user_setting(user.id, "monthly_salary", value)
        log_activity(update, "Sabit ayar değiştirdi", f"Personel maaşı: ₺{money(value)}")
        context.user_data.pop("awaiting_setting", None)
        message_id = context.user_data.pop("editor_message_id", None)
        try:
            await update.message.delete()
        except Exception:
            pass
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=message_id,
                    text=settings_screen_text(user.id),
                    parse_mode=ParseMode.HTML,
                    reply_markup=settings_keyboard(),
                )
                return
            except Exception as exc:
                logger.debug("Sabit ayar mesajı düzenlenemedi: %s", exc)
        await update.effective_chat.send_message(
            settings_screen_text(user.id), parse_mode=ParseMode.HTML, reply_markup=settings_keyboard()
        )
        return

    field = context.user_data.get("awaiting_field")
    if field not in NUMERIC_FIELDS:
        return
    raw = update.message.text or ""
    try:
        if field == "personnel":
            value = int(raw.strip())
            if value < 0:
                raise ValueError
        else:
            value = parse_decimal(raw)
            if value < 0:
                raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Geçerli ve negatif olmayan bir değer girin.")
        return

    data = get_calc_data(context)
    data[field] = value
    context.user_data.pop("awaiting_field", None)
    message_id = context.user_data.pop("editor_message_id", None)

    try:
        await update.message.delete()
    except Exception:
        pass

    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=message_id,
                text=calc_panel_text(data),
                parse_mode=ParseMode.HTML,
                reply_markup=calc_panel_keyboard(data),
            )
            return
        except Exception as exc:
            logger.debug("Panel mesajı düzenlenemedi: %s", exc)

    await update.effective_chat.send_message(
        calc_panel_text(data), parse_mode=ParseMode.HTML, reply_markup=calc_panel_keyboard(data)
    )


def result_text(result: Any, fuel_type: str, light_split: DutyLightSplit, history_id: int | None = None) -> str:
    saved = f"\n🗂 Kayıt no: <code>#{history_id}</code>" if history_id else ""
    return (
        "<b>✅ HESAPLAMA SONUCU</b>\n\n"
        f"🕒 Avara: <code>{result.departure}</code>\n"
        f"⚓ Aborda: <code>{result.arrival}</code>\n"
        f"⏱ Toplam süre: <b>{result.duration_text}</b>\n"
        f"🌙 Gece görev süresi: <b>{light_split.night_text}</b>\n"
        f"☀️ Gündüz görev süresi: <b>{light_split.day_text}</b>\n\n"
        f"🛢 Yakıt türü: <b>{fuel_type_label(fuel_type)}</b>\n"
        f"⚖️ Yakıt ağırlığı: <b>{money(result.fuel_kilograms)} kg</b>\n\n"
        f"🛠 Amortisman: <b>₺{money(result.amortization_cost_try)}</b>\n"
        f"👥 Personel: <b>₺{money(result.personnel_cost_try)}</b>\n"
        f"⛽ Yakıt maliyeti: <b>₺{money(result.fuel_cost_try)}</b>\n"
        f"💰 <b>TOPLAM: ₺{money(result.total_cost_try)}</b>"
        f"{saved}\n\n"
        "<b>GÖRRAP</b>\n"
        f"<code>{html.escape(result.gorrap_line)}</code>"
    )


def result_keyboard(gorrap_line: str, history_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📋 GÖRRAP satırını kopyala", copy_text=CopyTextButton(gorrap_line))],
    ]
    if history_id:
        rows.append([InlineKeyboardButton("🗂 Bu kaydı aç", callback_data=f"hist:view:{history_id}")])
    rows.extend(
        [
            [InlineKeyboardButton("🔄 Yeni hesaplama", callback_data="nav:new")],
            [
                InlineKeyboardButton("📚 Geçmiş", callback_data="nav:history:0"),
                InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu"),
            ],
        ]
    )
    return InlineKeyboardMarkup(rows)


async def run_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    data = get_calc_data(context)
    settings = get_user_settings(user.id)
    fuel_type = data.get("fuel_type", "diesel")
    if fuel_type not in FUEL_TYPES:
        fuel_type = "diesel"
        data["fuel_type"] = fuel_type

    fuel_province = settings["fuel_province"]
    solar_province = settings["solar_province"]
    monthly_salary = settings["monthly_salary"]

    snap = MARKET_STORE.get()
    fuel_price = snap.price_for(fuel_type, fuel_province)
    if not snap.ready_for(fuel_type, fuel_province) or fuel_price is None:
        # Ayar yeni değiştiyse hesap sırasında bir kez daha güncellemeyi dene.
        try:
            await asyncio.to_thread(MARKET_STORE.refresh, [fuel_province])
            snap = MARKET_STORE.get()
            fuel_price = snap.price_for(fuel_type, fuel_province)
        except Exception:
            logger.exception("Hesap öncesi otomatik veri yenilemesi başarısız")
    if not snap.ready_for(fuel_type, fuel_province) or fuel_price is None:
        await query.answer(
            f"Euro veya {fuel_province} {fuel_type_label(fuel_type).lower()} fiyatı henüz alınamadı. Otomatik Veriler ekranından yenilemeyi deneyin.",
            show_alert=True,
        )
        return

    effective_data = dict(data)
    effective_data["eur_rate"] = snap.eur_decimal
    effective_data["monthly_salary"] = monthly_salary
    effective_data["fuel_type"] = fuel_type
    effective_data["fuel_province"] = fuel_province
    effective_data["solar_province"] = solar_province
    effective_data["fuel_price"] = fuel_price

    try:
        result = calculate(
            departure=data["departure"],
            arrival=data["arrival"],
            eur_try=snap.eur_decimal,
            monthly_salary_try=monthly_salary,
            personnel_count=int(data["personnel"]),
            fuel_liters=data["fuel_liters"],
            fuel_price_try_per_liter=fuel_price,
            fuel_density_kg_per_l=fuel_density(fuel_type),
        )
        light_split = split_duty_by_daylight(
            result.departure,
            result.arrival,
            basis_date=datetime.now(TZ).date(),
            province=solar_province,
        )
        item_id = save_history(update, effective_data, result, light_split)
        log_activity(
            update,
            "Hesaplama yaptı",
            f"Kayıt #{item_id} • {fuel_type_label(fuel_type)} • Toplam ₺{money(result.total_cost_try)}",
        )
    except Exception as exc:
        logger.exception("Hesaplama hatası")
        await query.answer(f"Hesaplama yapılamadı: {exc}", show_alert=True)
        return

    await query.answer("Hesaplandı ve geçmişe kaydedildi.")
    await safe_edit(query, result_text(result, fuel_type, light_split, item_id), result_keyboard(result.gorrap_line, item_id))


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram Mini App'ten gelen form verisini işler ve hesaplar."""
    if not await require_auth(update):
        return
    message = update.effective_message
    if not message or not message.web_app_data:
        return

    raw_data = message.web_app_data.data
    try:
        payload = json.loads(raw_data)
    except Exception as exc:
        logger.warning("Geçersiz WebApp JSON verisi: %s", exc)
        await message.reply_text("⚠️ Mini App'ten geçersiz veri alındı.")
        return

    user = update.effective_user
    if not user:
        return

    departure_str = str(payload.get("departure", "")).strip()
    arrival_str = str(payload.get("arrival", "")).strip()
    departure2_str = str(payload.get("departure2", "")).strip()
    arrival2_str = str(payload.get("arrival2", "")).strip()
    
    personnel_val = payload.get("personnel", 4)
    fuel_liters_val = payload.get("fuel_liters", 750)
    fuel_liters2_val = payload.get("fuel_liters2")
    fuel_type = str(payload.get("fuel_type", "diesel")).strip().lower()
    duty_date_str = str(payload.get("duty_date", "")).strip()

    if fuel_type not in FUEL_TYPES:
        fuel_type = "diesel"

    duties = []
    try:
        personnel = int(personnel_val)
        if personnel < 1:
            raise ValueError

        duties_raw = payload.get("duties")
        if isinstance(duties_raw, list) and len(duties_raw) > 0:
            for idx, d in enumerate(duties_raw):
                dep_str = str(d.get("departure", "")).strip()
                arr_str = str(d.get("arrival", "")).strip()
                if not dep_str or not arr_str:
                    continue
                dep_norm = normalize_time(dep_str)
                arr_norm = normalize_time(arr_str)
                fl = parse_decimal(d.get("fuel_liters", 0))
                if fl < 0:
                    raise ValueError
                duties.append({
                    "dep": dep_norm,
                    "arr": arr_norm,
                    "fuel": fl,
                    "label": f"{idx + 1}. Görev",
                })
        else:
            dep_norm = normalize_time(departure_str)
            arr_norm = normalize_time(arrival_str)
            fuel_liters = parse_decimal(fuel_liters_val)
            if fuel_liters < 0:
                raise ValueError
            duties.append({"dep": dep_norm, "arr": arr_norm, "fuel": fuel_liters, "label": "1. Görev"})

            if departure2_str and arrival2_str and fuel_liters2_val is not None:
                dep2_norm = normalize_time(departure2_str)
                arr2_norm = normalize_time(arrival2_str)
                fuel_liters2 = parse_decimal(fuel_liters2_val)
                if fuel_liters2 < 0:
                    raise ValueError
                duties.append({"dep": dep2_norm, "arr": arr2_norm, "fuel": fuel_liters2, "label": "2. Görev"})

        if not duties:
            raise ValueError("En az bir geçerli görev girilmelidir.")

    except Exception:
        await message.reply_text("⚠️ Mini App verilerinde geçersiz saat, personel veya yakıt değeri.")
        return

    basis_date = datetime.now(TZ).date()
    if duty_date_str:
        try:
            basis_date = datetime.fromisoformat(duty_date_str).date()
        except Exception:
            pass

    settings = get_user_settings(user.id)
    fuel_province = settings["fuel_province"]
    solar_province = settings["solar_province"]
    monthly_salary = settings["monthly_salary"]

    snap = MARKET_STORE.get()
    fuel_price = snap.price_for(fuel_type, fuel_province)
    if not snap.ready_for(fuel_type, fuel_province) or fuel_price is None:
        try:
            await asyncio.to_thread(MARKET_STORE.refresh, [fuel_province])
            snap = MARKET_STORE.get()
            fuel_price = snap.price_for(fuel_type, fuel_province)
        except Exception:
            logger.exception("Hesap öncesi otomatik veri yenilemesi başarısız")

    if not snap.ready_for(fuel_type, fuel_province) or fuel_price is None:
        await message.reply_text(
            f"⚠️ Euro veya {fuel_province} {fuel_type_label(fuel_type).lower()} fiyatı henüz alınamadı.\n"
            "Lütfen <b>📡 Otomatik veriler</b> menüsünden yenilemeyi deneyin.",
            parse_mode=ParseMode.HTML,
        )
        return

    eur_rate = snap.eur_decimal
    density = fuel_density(fuel_type)

    for idx, duty in enumerate(duties):
        try:
            result = calculate(
                departure=duty["dep"],
                arrival=duty["arr"],
                eur_try=eur_rate,
                monthly_salary_try=monthly_salary,
                personnel_count=personnel,
                fuel_liters=duty["fuel"],
                fuel_price_try_per_liter=fuel_price,
                fuel_density_kg_per_l=density,
            )
            light_split = split_duty_by_daylight(
                departure=duty["dep"],
                arrival=duty["arr"],
                basis_date=basis_date,
                province=solar_province,
            )
        except Exception as exc:
            logger.exception("Mini App hesaplama hatası (%s)", duty["label"])
            await message.reply_text(f"⚠️ {duty['label']} hesaplama hatası: {html.escape(str(exc))}")
            continue

        data_record = {
            "departure": duty["dep"],
            "arrival": duty["arr"],
            "eur_rate": eur_rate,
            "monthly_salary": monthly_salary,
            "personnel": personnel,
            "fuel_liters": duty["fuel"],
            "fuel_type": fuel_type,
            "fuel_province": fuel_province,
            "solar_province": solar_province,
            "fuel_price": fuel_price,
        }

        # Kullanıcının son girdiği panel verisini güncelle (her zaman son görevi panelde tutar)
        context.user_data["calc"] = {
            "departure": duty["dep"],
            "arrival": duty["arr"],
            "personnel": personnel,
            "fuel_liters": duty["fuel"],
            "fuel_type": fuel_type,
        }

        history_id = save_history(update, data_record, result, light_split)
        
        log_activity(
            update,
            f"Mini App ile {duty['label']} hesapladı",
            f"Kayıt #{history_id} • {fuel_type_label(fuel_type)} • ₺{money(result.total_cost_try)}",
        )

        title = "📱 <b>Mini App ile Hesaplandı</b>"
        if len(duties) > 1:
            title = f"📱 <b>Mini App - {duty['label']}</b>"
            
        out_text = f"{title}\n\n" + result_text(result, fuel_type, light_split, history_id)
        markup = result_keyboard(result.gorrap_line, history_id)
        
        await message.reply_text(out_text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def open_webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcıya Mini App açma butonunu gönderir."""
    if not await require_auth(update):
        return
    if not update.effective_message:
        return
    if not WEBAPP_URL:
        await update.effective_message.reply_text(
            "⚠️ <b>Mini App URL'si tanımlı değil.</b>\n\n"
            "Mini App'i kullanabilmek için <code>WEBAPP_URL</code> ayarını (örn: GitHub Pages veya HTTPS linkinizi) yapılandırın.",
            parse_mode=ParseMode.HTML,
        )
        return

    markup = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Mini App Aç", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True
    )
    await update.effective_message.reply_text(
        "<b>📱 GÖREV MALİYET MİNİ APP</b>\n\n"
        "Alt kısımda (klavye alanında) beliren <b>📱 Mini App Aç</b> butonuna dokunarak formu doldurabilirsiniz. "
        "Form gönderildiğinde sonuçlar doğrudan buraya yansıyacaktır.",
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def load_example(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    context.user_data["calc"] = fresh_calc_data()
    await query.answer("Örnek günlük değerler yüklendi.")
    data = get_calc_data(context)
    await safe_edit(query, calc_panel_text(data), calc_panel_keyboard(data))


async def load_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    last = latest_inputs(user.id)
    if not last:
        await query.answer("Henüz geçmiş hesaplama yok.", show_alert=True)
        return
    context.user_data["calc"] = last
    await query.answer("Son hesaplamadaki değerler yüklendi.")
    await safe_edit(query, calc_panel_text(last), calc_panel_keyboard(last))


def format_history_date(iso_value: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_value)
        return dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso_value[:16].replace("T", " ")


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    if not await require_auth(update):
        return
    user = update.effective_user
    if not user:
        return
    total = history_count(user.id)
    max_page = max(0, (total - 1) // HISTORY_PAGE_SIZE) if total else 0
    page = max(0, min(page, max_page))
    rows = history_page(user.id, page)

    text = f"<b>📚 GEÇMİŞ HESAPLAMALAR</b>\n\nToplam kayıt: <b>{total}</b>"
    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        label = f"#{row['id']} • {format_history_date(row['created_at'])} • ₺{money(row['total_cost'])}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"hist:view:{row['id']}")])

    if not rows:
        text += "\n\nHenüz kayıtlı hesaplama yok."

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Önceki", callback_data=f"nav:history:{page - 1}"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton("Sonraki ➡️", callback_data=f"nav:history:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    if total:
        keyboard.append([InlineKeyboardButton("🗑 Geçmişi temizle", callback_data="hist:clear:ask")])
    keyboard.append([InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")])
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, text, markup)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


def history_light_split(row: sqlite3.Row) -> DutyLightSplit:
    keys = set(row.keys())
    if {"day_minutes", "night_minutes", "solar_basis_date"}.issubset(keys):
        if row["day_minutes"] is not None and row["night_minutes"] is not None and row["solar_basis_date"]:
            try:
                return DutyLightSplit(
                    basis_date=datetime.fromisoformat(str(row["solar_basis_date"])).date(),
                    day_minutes=int(row["day_minutes"]),
                    night_minutes=int(row["night_minutes"]),
                    province_name=str(row["solar_province"] or "Samsun") if "solar_province" in keys else "Samsun",
                )
            except Exception:
                pass
    try:
        basis = datetime.fromisoformat(row["created_at"]).astimezone(TZ).date()
    except Exception:
        basis = datetime.now(TZ).date()
    province = str(row["solar_province"] or "Samsun") if "solar_province" in keys else "Samsun"
    return split_duty_by_daylight(row["departure"], row["arrival"], basis_date=basis, province=province)


async def show_history_item(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    row = history_item(user.id, item_id)
    if not row:
        await query.answer("Kayıt bulunamadı.", show_alert=True)
        return
    await query.answer()
    saved_fuel_type = row["fuel_type"] if row["fuel_type"] in FUEL_TYPES else "diesel"
    saved_fuel_kg = Decimal(row["fuel_liters"]) * fuel_density(saved_fuel_type)
    light_split = history_light_split(row)
    text = (
        f"<b>🗂 HESAP KAYDI #{row['id']}</b>\n"
        f"<i>{format_history_date(row['created_at'])}</i>\n\n"
        f"🕒 Avara: <code>{html.escape(row['departure'])}</code>\n"
        f"⚓ Aborda: <code>{html.escape(row['arrival'])}</code>\n"
        f"⏱ Toplam süre: <b>{html.escape(row['duration_text'])}</b>\n"
        f"🌙 Gece görev süresi: <b>{light_split.night_text}</b>\n"
        f"☀️ Gündüz görev süresi: <b>{light_split.day_text}</b>\n\n"
        f"🛢 Yakıt türü: <b>{fuel_type_label(saved_fuel_type)}</b>\n"
        f"⚖️ Yakıt ağırlığı: <b>{money(saved_fuel_kg)} kg</b>\n"
        f"⛽ Fiyat ili: {html.escape(str(row['fuel_province'] or 'Samsun'))}\n"
        f"🌅 Güneş ili: {html.escape(str(row['solar_province'] or 'Samsun'))}\n"
        f"💶 Euro: ₺{money(row['eur_rate'])}\n"
        f"💼 Maaş: ₺{money(row['monthly_salary'])}\n"
        f"👥 Personel: {row['personnel']}\n"
        f"⛽ Yakıt: {money(row['fuel_liters'])} L\n"
        f"💰 Litre fiyatı: ₺{money(row['fuel_price'])}\n\n"
        f"🛠 Amortisman: <b>₺{money(row['amortization_cost'])}</b>\n"
        f"👥 Personel: <b>₺{money(row['personnel_cost'])}</b>\n"
        f"⛽ Yakıt maliyeti: <b>₺{money(row['fuel_cost'])}</b>\n"
        f"💰 <b>TOPLAM: ₺{money(row['total_cost'])}</b>\n\n"
        "<b>GÖRRAP</b>\n"
        f"<code>{html.escape(row['gorrap_line'])}</code>"
    )
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 GÖRRAP satırını kopyala", copy_text=CopyTextButton(row["gorrap_line"]))],
            [InlineKeyboardButton("♻️ Bu değerlerle yeni hesap", callback_data=f"hist:reuse:{row['id']}")],
            [InlineKeyboardButton("↩️ Geçmişe dön", callback_data="nav:history:0")],
            [InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")],
        ]
    )
    await safe_edit(query, text, markup)


async def reuse_history_item(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    row = history_item(user.id, item_id)
    if not row:
        await query.answer("Kayıt bulunamadı.", show_alert=True)
        return
    data = {
        "departure": row["departure"],
        "arrival": row["arrival"],
        "personnel": int(row["personnel"]),
        "fuel_liters": Decimal(row["fuel_liters"]),
        "fuel_type": row["fuel_type"] if row["fuel_type"] in FUEL_TYPES else "diesel",
    }
    context.user_data["calc"] = data
    await query.answer("Kayıttaki değerler yüklendi.")
    await safe_edit(query, calc_panel_text(data), calc_panel_keyboard(data))


async def ask_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑 Evet, tümünü sil", callback_data="hist:clear:yes")],
            [InlineKeyboardButton("↩️ Vazgeç", callback_data="nav:history:0")],
        ]
    )
    await safe_edit(
        query,
        "<b>⚠️ Geçmişi temizle</b>\n\nSize ait tüm hesaplama kayıtları kalıcı olarak silinecek. Emin misiniz?",
        markup,
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Yenile", callback_data="admin:panel"),
                InlineKeyboardButton("👥 Kullanıcılar", callback_data="admin:users"),
            ],
            [InlineKeyboardButton("🕘 Son İşlemler", callback_data="admin:activity")],
            [InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")],
        ]
    )


def admin_panel_text() -> str:
    stats = admin_dashboard_stats()
    rows = recent_activity(8)
    lines = [
        "<b>👑 YÖNETİCİ PANELİ</b>",
        "",
        f"🧮 Bugünkü hesaplama: <b>{stats['today_calcs']}</b>",
        f"📚 Toplam hesaplama: <b>{stats['total_calcs']}</b>",
        f"👥 İşlem yapan kullanıcı: <b>{stats['distinct_users']}</b>",
        f"🧾 Kaydedilen işlem: <b>{stats['total_actions']}</b>",
        "",
        "<b>Son kullanıcı işlemleri</b>",
    ]
    if not rows:
        lines.append("Henüz işlem kaydı yok.")
    else:
        for row in rows:
            identity = _admin_identity(row)
            detail = f" — {html.escape(row['detail'])}" if row['detail'] else ""
            lines.append(
                f"• {_admin_dt(row['created_at'])} — {identity}\n"
                f"  {html.escape(row['action'])}{detail}"
            )
    return "\n".join(lines)


async def _admin_guard(update: Update) -> bool:
    if is_admin(update):
        return True
    if update.callback_query:
        await update.callback_query.answer("Bu bölüm yalnızca yöneticiye açıktır.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("⛔ Bu bölüm yalnızca yöneticiye açıktır.")
    return False


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update):
        return
    context.user_data.pop("awaiting_admin_name_user_id", None)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, admin_panel_text(), admin_panel_keyboard())
    else:
        await update.effective_message.reply_text(
            admin_panel_text(), parse_mode=ParseMode.HTML, reply_markup=admin_panel_keyboard()
        )


def admin_users_keyboard(rows: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        custom_name = str(row["custom_name"] or "").strip()
        username = str(row["username"] or "").strip()
        full_name = str(row["full_name"] or "").strip()
        label = custom_name or (f"@{username}" if username else full_name) or f"Kullanıcı {row['user_id']}"
        if len(label) > 32:
            label = label[:29] + "…"
        keyboard.append([InlineKeyboardButton(f"👤 {label}", callback_data=f"admin:user:{row['user_id']}")])
    keyboard.extend(
        [
            [InlineKeyboardButton("🔄 Yenile", callback_data="admin:users")],
            [InlineKeyboardButton("↩️ Yönetici Paneli", callback_data="admin:panel")],
        ]
    )
    return InlineKeyboardMarkup(keyboard)


async def show_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update):
        return
    context.user_data.pop("awaiting_admin_name_user_id", None)
    rows = admin_user_summary(30)
    lines = ["<b>👥 KULLANICILAR</b>", "", "Bir kullanıcıya dokunarak özel isim verebilir veya değiştirebilirsiniz.", ""]
    if not rows:
        lines.append("Henüz kullanıcı işlemi yok.")
    else:
        for row in rows:
            lines.append(
                f"{_admin_identity(row)}\n"
                f"  🧮 {int(row['calculation_count'] or 0)} hesap • 🧾 {int(row['action_count'] or 0)} işlem\n"
                f"  Son kullanım: {_admin_dt(row['last_seen'])}"
            )
    markup = admin_users_keyboard(rows)
    text = "\n\n".join(lines)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, text, markup)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


def admin_user_detail_text(user_id: int) -> str:
    row = admin_user_detail(user_id)
    if not row:
        return "<b>👤 KULLANICI</b>\n\nKullanıcı kaydı bulunamadı."
    custom_name = str(row["custom_name"] or "").strip()
    username = str(row["username"] or "").strip()
    full_name = str(row["full_name"] or "").strip()
    lines = [
        "<b>👤 KULLANICI DETAYI</b>",
        "",
        f"Görünen isim: <b>{html.escape(custom_name) if custom_name else 'Henüz verilmedi'}</b>",
        f"Telegram ID: <code>{user_id}</code>",
    ]
    if username:
        lines.append(f"Telegram kullanıcı adı: @{html.escape(username)}")
    if full_name:
        lines.append(f"Telegram adı: {html.escape(full_name)}")
    lines.extend(
        [
            "",
            f"🧮 Hesaplama: <b>{int(row['calculation_count'] or 0)}</b>",
            f"🧾 Toplam işlem: <b>{int(row['action_count'] or 0)}</b>",
            f"İlk kullanım: {_admin_dt(row['first_seen'])}",
            f"Son kullanım: {_admin_dt(row['last_seen'])}",
        ]
    )
    return "\n".join(lines)


def admin_user_detail_keyboard(user_id: int) -> InlineKeyboardMarkup:
    row = admin_user_detail(user_id)
    has_name = bool(row and str(row["custom_name"] or "").strip())
    keyboard = [[InlineKeyboardButton("✏️ İsim ver / değiştir", callback_data=f"admin:name:{user_id}")]]
    if has_name:
        keyboard.append([InlineKeyboardButton("🗑 Verdiğim ismi kaldır", callback_data=f"admin:delname:{user_id}")])
    keyboard.extend(
        [
            [InlineKeyboardButton("↩️ Kullanıcılara dön", callback_data="admin:users")],
            [InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")],
        ]
    )
    return InlineKeyboardMarkup(keyboard)


async def show_admin_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    if not await _admin_guard(update):
        return
    context.user_data.pop("awaiting_admin_name_user_id", None)
    query = update.callback_query
    if not query:
        return
    await query.answer()
    await safe_edit(query, admin_user_detail_text(user_id), admin_user_detail_keyboard(user_id))


async def ask_admin_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    if not await _admin_guard(update):
        return
    query = update.callback_query
    if not query:
        return
    if not admin_user_detail(user_id):
        await query.answer("Kullanıcı bulunamadı.", show_alert=True)
        return
    context.user_data["awaiting_admin_name_user_id"] = user_id
    context.user_data["editor_message_id"] = query.message.message_id if query.message else None
    await query.answer()
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Vazgeç", callback_data=f"admin:user:{user_id}")]])
    await safe_edit(
        query,
        "<b>✏️ Kullanıcıya isim ver</b>\n\nPanelde görmek istediğiniz ismi mesaj olarak gönderin.\nÖrnek: <code>Kaptan Ahmet</code>",
        markup,
    )


async def delete_admin_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    if not await _admin_guard(update):
        return
    query = update.callback_query
    if not query:
        return
    delete_admin_user_label(user_id)
    context.user_data.pop("awaiting_admin_name_user_id", None)
    log_activity(update, "Yönetim ayarı güncellendi", f"Kullanıcı {user_id}: görünen ad kaldırıldı")
    await query.answer("İsim kaldırıldı.")
    await safe_edit(query, admin_user_detail_text(user_id), admin_user_detail_keyboard(user_id))


async def show_admin_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update):
        return
    rows = recent_activity(25)
    lines = ["<b>🕘 SON İŞLEMLER</b>", ""]
    if not rows:
        lines.append("Henüz işlem kaydı yok.")
    else:
        for row in rows:
            who = _admin_identity(row)
            detail = f" — {html.escape(row['detail'])}" if row['detail'] else ""
            lines.append(
                f"{_admin_dt(row['created_at'])} • {who}\n"
                f"{html.escape(row['action'])}{detail}"
            )
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Yenile", callback_data="admin:activity")],
            [InlineKeyboardButton("↩️ Yönetici Paneli", callback_data="admin:panel")],
        ]
    )
    text = "\n\n".join(lines)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, text, markup)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def do_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    clear_history(user.id)
    total = history_count(user.id)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menü", callback_data="nav:menu")]])
    await query.answer("Geçmiş silindi.")
    await safe_edit(query, f"<b>📚 GEÇMİŞ HESAPLAMALAR</b>\n\nToplam kayıt: <b>{total}</b>\n\nHenüz kayıtlı hesaplama yok.", markup)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data
    parts = data.split(":")

    if data == "nav:menu":
        await show_main_menu(update, context)
    elif data == "nav:new":
        await start_new_calc(update, context)
    elif data == "nav:settings":
        await show_settings(update, context)
    elif data.startswith("nav:history:"):
        await show_history(update, context, int(parts[2]))
    elif data == "nav:constants":
        await show_constants(update, context)
    elif data == "nav:data":
        await show_automatic_data(update, context)
    elif data == "settings:salary":
        await show_salary_settings(update, context)
    elif data.startswith("settings:salary:"):
        await handle_salary_setting_action(update, context, parts)
    elif data.startswith("settings:prov:") and len(parts) == 4:
        await show_province_picker(update, context, parts[2], int(parts[3]))
    elif data.startswith("settings:setprov:") and len(parts) == 4:
        await set_province_setting(update, context, parts[2], parts[3])
    elif data == "settings:noop":
        await query.answer()
    elif data == "data:refresh":
        await refresh_automatic_data(update, context)
    elif data == "back:calc":
        await show_calc_panel(update, context)
    elif data.startswith("edit:") and len(parts) == 2:
        await edit_field(update, context, parts[1])
    elif data.startswith("fuel:") and len(parts) == 2:
        await set_fuel_type(update, context, parts[1])
    elif data.startswith("time:"):
        await handle_time_action(update, context, parts)
    elif data.startswith("num:"):
        await handle_numeric_action(update, context, parts)
    elif data == "calc:run":
        await run_calculation(update, context)
    elif data == "calc:example":
        await load_example(update, context)
    elif data == "calc:last":
        await load_last(update, context)
    elif data.startswith("hist:view:"):
        await show_history_item(update, context, int(parts[2]))
    elif data.startswith("hist:reuse:"):
        await reuse_history_item(update, context, int(parts[2]))
    elif data == "hist:clear:ask":
        await ask_clear_history(update, context)
    elif data == "hist:clear:yes":
        await do_clear_history(update, context)
    elif data.startswith("admin:user:") and len(parts) == 3:
        await show_admin_user_detail(update, context, int(parts[2]))
    elif data.startswith("admin:name:") and len(parts) == 3:
        await ask_admin_user_name(update, context, int(parts[2]))
    elif data.startswith("admin:delname:") and len(parts) == 3:
        await delete_admin_user_name(update, context, int(parts[2]))
    elif data == "admin:panel":
        await show_admin_panel(update, context)
    elif data == "admin:users":
        await show_admin_users(update, context)
    elif data == "admin:activity":
        await show_admin_activity(update, context)
    else:
        await query.answer("Bilinmeyen işlem.", show_alert=True)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update):
        return
    context.user_data.pop("awaiting_field", None)
    context.user_data.pop("awaiting_setting", None)
    context.user_data.pop("awaiting_admin_name_user_id", None)
    context.user_data.pop("editor_message_id", None)
    user_id = update.effective_user.id if update.effective_user else None
    await update.effective_message.reply_text("İşlem iptal edildi.", reply_markup=main_menu_keyboard(user_id))


async def market_refresh_loop() -> None:
    while True:
        now = datetime.now(TZ)
        next_run = datetime.combine(now.date(), time(AUTO_REFRESH_HOUR, AUTO_REFRESH_MINUTE), tzinfo=TZ)
        if now >= next_run:
            next_run += timedelta(days=1)
        delay = max(1.0, (next_run - now).total_seconds())
        logger.info("Bir sonraki otomatik piyasa verisi güncellemesi: %s", next_run.isoformat(timespec="minutes"))
        await asyncio.sleep(delay)
        try:
            provinces = configured_fuel_provinces()
            result = await asyncio.to_thread(MARKET_STORE.refresh, provinces)
            snap = result["snapshot"]
            logger.info(
                "Günlük otomatik veri kontrolü tamamlandı. EUR=%s, iller=%s",
                snap.eur_try,
                ", ".join(provinces),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Günlük otomatik veri güncellemesi beklenmeyen hata verdi")


async def post_init(application: Application) -> None:
    try:
        provinces = configured_fuel_provinces()
        result = await asyncio.to_thread(MARKET_STORE.refresh, provinces)
        snap = result["snapshot"]
        logger.info(
            "Açılış piyasa verisi kontrolü tamamlandı. EUR=%s, iller=%s",
            snap.eur_try,
            ", ".join(provinces),
        )
    except Exception:
        logger.exception("Açılışta piyasa verileri güncellenemedi; varsa önbellek kullanılacak")

    # Explicitly clear any cached MenuButtonWebApp since tg.sendData() ONLY works via ReplyKeyboardMarkup
    try:
        from telegram import MenuButtonCommands
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:
        pass

    application.bot_data["market_refresh_task"] = asyncio.create_task(market_refresh_loop())


async def post_shutdown(application: Application) -> None:
    task = application.bot_data.get("market_refresh_task")
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tanımlı değil. BotFather token'ını .env dosyasına ekleyin.")

    init_db()
    if not ALLOW_ALL_USERS and not AUTHORIZED_USER_IDS:
        logger.warning(
            "AUTHORIZED_USER_IDS boş. /id komutu kullanıcı ID'sini gösterir; ID eklenene kadar kimse hesaplama yapamaz."
        )

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", show_main_menu))
    application.add_handler(CommandHandler("menu", show_main_menu))
    application.add_handler(CommandHandler("hesapla", start_new_calc))
    application.add_handler(CommandHandler("webapp", open_webapp_command))
    application.add_handler(CommandHandler("miniapp", open_webapp_command))
    application.add_handler(CommandHandler("ayarlar", show_settings))
    application.add_handler(CommandHandler("gecmis", show_history))
    application.add_handler(CommandHandler("sabitler", show_constants))
    application.add_handler(CommandHandler("veriler", show_automatic_data))
    application.add_handler(CommandHandler("id", show_identity))
    application.add_handler(CommandHandler("yonetici", show_admin_panel))
    application.add_handler(CommandHandler("iptal", cancel))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_value_received))

    logger.info("Bot başlatıldı. Veritabanı: %s | Otomatik veri önbelleği: %s", DB_PATH, MARKET_DATA_PATH)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
