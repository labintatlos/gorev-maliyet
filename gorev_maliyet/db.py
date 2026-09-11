"""SQLite şeması ve ortak veri erişimi.

Veritabanı Home Assistant'ta `/share/gorev_maliyet/` altında durur; eklenti
güncellense veya yeniden kurulsa da silinmez. Oturum imza anahtarı, kurulum
kodu ve piyasa verisi önbelleği de aynı klasördedir.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


def _data_dir():
    override = os.environ.get('GOREV_MALIYET_DATA')
    if override:
        return Path(override)
    if Path('/share').is_dir():
        return Path('/share/gorev_maliyet')
    return Path('.')


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / 'gorev_maliyet.db'


def now_iso():
    return datetime.now().isoformat(timespec='seconds')


@contextmanager
def session():
    """İşlemi commit/rollback eder ve bağlantıyı her durumda kapatır."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS web_accounts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    ha_user TEXT,
    created_at TEXT,
    last_login TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    position TEXT,
    approval_status TEXT NOT NULL DEFAULT 'approved',
    reviewed_at TEXT,
    reviewed_by INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_web_accounts_email
    ON web_accounts(email COLLATE NOCASE) WHERE email IS NOT NULL AND email != '';

CREATE TABLE IF NOT EXISTS password_reset_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_password_reset_pending
    ON password_reset_requests(account_id) WHERE state='pending';

CREATE TABLE IF NOT EXISTS activity_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_log_id ON activity_log(id DESC);

CREATE TABLE IF NOT EXISTS issue_reports(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by INTEGER
);
CREATE INDEX IF NOT EXISTS idx_issue_reports_status ON issue_reports(status, id DESC);

CREATE TABLE IF NOT EXISTS user_settings(
    account_id INTEGER PRIMARY KEY,
    fuel_province TEXT NOT NULL,
    solar_province TEXT NOT NULL,
    monthly_salary TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calculations(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    batch_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    duty_date TEXT NOT NULL,
    departure TEXT NOT NULL,
    arrival TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    day_minutes INTEGER NOT NULL,
    night_minutes INTEGER NOT NULL,
    personnel INTEGER NOT NULL,
    fuel_type TEXT NOT NULL,
    fuel_liters TEXT NOT NULL,
    fuel_province TEXT NOT NULL,
    solar_province TEXT NOT NULL,
    fuel_price TEXT NOT NULL,
    eur_rate TEXT NOT NULL,
    monthly_salary TEXT NOT NULL,
    amortization_cost TEXT NOT NULL,
    personnel_cost TEXT NOT NULL,
    fuel_cost TEXT NOT NULL,
    total_cost TEXT NOT NULL,
    gorrap_line TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calculations_account ON calculations(account_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_calculations_batch ON calculations(account_id, batch_id);
'''


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with session() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript(SCHEMA)


# ── İşlem kayıtları ──────────────────────────────────────────────────────

def log_activity(account_id, action, detail=''):
    """Güvenli işlem kaydı; parola ve oturum verisi almaz."""
    detail = ' '.join(str(detail or '').split())[:240]
    with session() as c:
        c.execute('INSERT INTO activity_log(account_id,action,detail,created_at) VALUES(?,?,?,?)',
                  (account_id, str(action)[:40], detail, now_iso()))


def recent_activity(limit=40):
    with session() as c:
        return c.execute('''
            SELECT a.id, a.account_id, a.action, a.detail, a.created_at,
                   COALESCE(w.display_name, 'Bilinmeyen kişi') AS display_name,
                   COALESCE(w.username, '') AS username
            FROM activity_log a
            LEFT JOIN web_accounts w ON w.id = a.account_id
            ORDER BY a.id DESC
            LIMIT ?
        ''', (int(limit),)).fetchall()


# ── Sorun bildirimleri ───────────────────────────────────────────────────

def create_issue_report(account_id, message):
    with session() as c:
        cur = c.execute("INSERT INTO issue_reports(account_id,message,status,created_at) VALUES(?,?,'open',?)",
                        (account_id, message, now_iso()))
        return cur.lastrowid


def open_issue_reports(limit=30):
    with session() as c:
        return c.execute('''
            SELECT r.id, r.message, r.created_at,
                   COALESCE(w.display_name, 'Bilinmeyen kişi') AS display_name,
                   COALESCE(w.username, '') AS username
            FROM issue_reports r
            LEFT JOIN web_accounts w ON w.id = r.account_id
            WHERE r.status='open'
            ORDER BY r.id DESC LIMIT ?
        ''', (int(limit),)).fetchall()


def resolve_issue_report(report_id, account_id):
    with session() as c:
        cur = c.execute("UPDATE issue_reports SET status='resolved',resolved_at=?,resolved_by=? WHERE id=? AND status='open'",
                        (now_iso(), account_id, int(report_id)))
        return cur.rowcount > 0
