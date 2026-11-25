
import os, sqlite3, hashlib, hmac, base64, json, secrets, pathlib, datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.getenv('DATA_DIR', str(BASE / 'data')))
DATA.mkdir(exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
USE_PG = bool(DATABASE_URL)
SECRET = os.getenv('APP_SECRET', 'change-this-secret-in-production').encode()
COOKIE = 'qvc_session'
COOKIE_SECURE = os.getenv('COOKIE_SECURE', '1' if USE_PG else '0') == '1'
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '').strip()
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '').strip()
VAPID_EMAIL = os.getenv('VAPID_EMAIL', 'mailto:admin@example.com').strip()
VN_TZ = ZoneInfo('Asia/Ho_Chi_Minh')
app = FastAPI(title='Quản lý Văn bản & Công việc')

class DB:
    def __init__(self):
        if USE_PG:
            import psycopg
            from psycopg.rows import dict_row
            self.conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
            self.pg = True
        else:
            self.conn = sqlite3.connect(DATA / 'app.db')
            self.conn.row_factory = sqlite3.Row
            self.pg = False
    def execute(self, sql, params=()):
        if self.pg: sql = sql.replace('?', '%s')
        return self.conn.execute(sql, params)
    def commit(self): self.conn.commit()
    def close(self): self.conn.close()

def now_iso(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def hp(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    return salt.hex() + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000).hex()
def vp(password, value):
    try:
        salt, digest = value.split(':')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 210000).hex()
        return hmac.compare_digest(actual, digest)
    except Exception: return False
def tok(user_id):
    raw = json.dumps({'uid': user_id, 'exp': int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 86400}, separators=(',', ':')).encode()
    b = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    return b + '.' + hmac.new(SECRET, b.encode(), hashlib.sha256).hexdigest()
def uid(token):
    try:
        b, sig = token.split('.')
        if not hmac.compare_digest(hmac.new(SECRET, b.encode(), hashlib.sha256).hexdigest(), sig): return None
        payload = json.loads(base64.urlsafe_b64decode(b + '==='))
        if payload['exp'] < int(datetime.datetime.now(datetime.timezone.utc).timestamp()): return None
        return int(payload['uid'])
    except Exception: return None

def init():
    c = DB()
    if c.pg:
        statements = [
            "CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY,user_name TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'Người dùng',active BOOLEAN NOT NULL DEFAULT TRUE,created_at TEXT NOT NULL)",
            'CREATE TABLE IF NOT EXISTS docs (id BIGSERIAL PRIMARY KEY,owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,date TEXT,no TEXT,title TEXT,due TEXT,secret TEXT,status TEXT,created_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS tasks (id BIGSERIAL PRIMARY KEY,owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,title TEXT,time TEXT,status TEXT,created_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS settings (user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,reminder_minutes INTEGER DEFAULT 60,overdue BOOLEAN DEFAULT TRUE,screen_notify BOOLEAN DEFAULT TRUE,sound_notify BOOLEAN DEFAULT TRUE,voice_notify BOOLEAN DEFAULT TRUE)',
            'CREATE TABLE IF NOT EXISTS push_subscriptions (id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,endpoint TEXT UNIQUE NOT NULL,p256dh TEXT NOT NULL,auth TEXT NOT NULL,created_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS notification_log (id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,record_id BIGINT NOT NULL,notification_type TEXT NOT NULL,due_at TEXT NOT NULL,reminder_minutes INTEGER NOT NULL DEFAULT 0,sent_at TEXT NOT NULL,UNIQUE(user_id,kind,record_id,notification_type,due_at,reminder_minutes))'
        ]
    else:
        statements = [
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,user_name TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'Người dùng',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL)",
            'CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,date TEXT,no TEXT,title TEXT,due TEXT,secret TEXT,status TEXT,created_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,title TEXT,time TEXT,status TEXT,created_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY,reminder_minutes INTEGER DEFAULT 60,overdue INTEGER DEFAULT 1,screen_notify INTEGER DEFAULT 1,sound_notify INTEGER DEFAULT 1,voice_notify INTEGER DEFAULT 1)',
            'CREATE TABLE IF NOT EXISTS push_subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,endpoint TEXT UNIQUE NOT NULL,p256dh TEXT NOT NULL,auth TEXT NOT NULL,created_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS notification_log (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,kind TEXT NOT NULL,record_id INTEGER NOT NULL,notification_type TEXT NOT NULL,due_at TEXT NOT NULL,reminder_minutes INTEGER NOT NULL DEFAULT 0,sent_at TEXT NOT NULL,UNIQUE(user_id,kind,record_id,notification_type,due_at,reminder_minutes))'
        ]
    for q in statements: c.execute(q)
    if c.pg:
        c.execute('DROP TABLE IF EXISTS files')
        c.execute('ALTER TABLE docs DROP COLUMN IF EXISTS file_id')
        c.execute('ALTER TABLE docs DROP COLUMN IF EXISTS file_name')
        c.execute('ALTER TABLE tasks DROP COLUMN IF EXISTS file_id')
        c.execute('ALTER TABLE tasks DROP COLUMN IF EXISTS file_name')
    if not c.execute('SELECT id FROM users WHERE user_name=?', ('NongVanHuy',)).fetchone():
        c.execute('INSERT INTO users(user_name,name,password,role,active,created_at) VALUES(?,?,?,?,?,?)', ('NongVanHuy','Quản trị viên',hp('11011998Huy@'),'Quản trị',True,now_iso()))
    # Sua loi quyen: dong bo vai tro tai khoan quan tri chinh moi lan khoi dong.
    c.execute('UPDATE users SET role=?, active=? WHERE user_name=?', ('Quản trị', True, 'NongVanHuy'))
    c.commit()
    c.close()
init()
