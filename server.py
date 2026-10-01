import os, sqlite3, hashlib, hmac, base64, json, secrets, pathlib, datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
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
    c=DB()
    if c.pg:
        statements=[
            """CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY,user_name TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'Người dùng',active BOOLEAN NOT NULL DEFAULT TRUE,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS docs (id BIGSERIAL PRIMARY KEY,owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,date TEXT,no TEXT,title TEXT,due TEXT,secret TEXT,status TEXT,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS tasks (id BIGSERIAL PRIMARY KEY,owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,title TEXT,time TEXT,status TEXT,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS settings (user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,reminder_minutes INTEGER DEFAULT 60,overdue BOOLEAN DEFAULT TRUE,screen_notify BOOLEAN DEFAULT TRUE,sound_notify BOOLEAN DEFAULT TRUE,voice_notify BOOLEAN DEFAULT TRUE)""",
            """CREATE TABLE IF NOT EXISTS push_subscriptions (id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,endpoint TEXT UNIQUE NOT NULL,p256dh TEXT NOT NULL,auth TEXT NOT NULL,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS notification_log (id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,record_id BIGINT NOT NULL,notification_type TEXT NOT NULL,due_at TEXT NOT NULL,reminder_minutes INTEGER NOT NULL DEFAULT 0,sent_at TEXT NOT NULL,UNIQUE(user_id,kind,record_id,notification_type,due_at,reminder_minutes))"""
        ]
    else:
        statements=[
            """CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,user_name TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'Người dùng',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,date TEXT,no TEXT,title TEXT,due TEXT,secret TEXT,status TEXT,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,title TEXT,time TEXT,status TEXT,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY,reminder_minutes INTEGER DEFAULT 60,overdue INTEGER DEFAULT 1,screen_notify INTEGER DEFAULT 1,sound_notify INTEGER DEFAULT 1,voice_notify INTEGER DEFAULT 1)""",
            """CREATE TABLE IF NOT EXISTS push_subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,endpoint TEXT UNIQUE NOT NULL,p256dh TEXT NOT NULL,auth TEXT NOT NULL,created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS notification_log (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,kind TEXT NOT NULL,record_id INTEGER NOT NULL,notification_type TEXT NOT NULL,due_at TEXT NOT NULL,reminder_minutes INTEGER NOT NULL DEFAULT 0,sent_at TEXT NOT NULL,UNIQUE(user_id,kind,record_id,notification_type,due_at,reminder_minutes))"""
        ]
    for q in statements: c.execute(q)
    if c.pg:
        # Phiên bản v3 không lưu file; dọn schema file cũ nếu database đã chạy bản trước.
        c.execute('DROP TABLE IF EXISTS files')
        c.execute('ALTER TABLE docs DROP COLUMN IF EXISTS file_id')
        c.execute('ALTER TABLE docs DROP COLUMN IF EXISTS file_name')
        c.execute('ALTER TABLE tasks DROP COLUMN IF EXISTS file_id')
        c.execute('ALTER TABLE tasks DROP COLUMN IF EXISTS file_name')
    if not c.execute("SELECT id FROM users WHERE user_name=?",('NongVanHuy',)).fetchone():
        c.execute("INSERT INTO users(user_name,name,password,role,active,created_at) VALUES(?,?,?,?,?,?)",('NongVanHuy','Quản trị viên',hp('11011998Huy@'),'Quản trị',True,now_iso()))
    c.commit(); c.close()
init()

def me(request):
    user_id=uid(request.cookies.get(COOKIE,''))
    if not user_id: raise HTTPException(401,'Chưa đăng nhập')
    c=DB(); u=c.execute('SELECT id,user_name,name,role,active FROM users WHERE id=?',(user_id,)).fetchone(); c.close()
    if not u or not u['active']: raise HTTPException(401,'Tài khoản không hợp lệ')
    return dict(u)

def adm(user):
    if user['role']!='Quản trị': raise HTTPException(403,'Chỉ quản trị viên được phép thực hiện')

def user_only(user):
    if user['role']=='Quản trị': raise HTTPException(403,'Tài khoản quản trị chỉ quản lý tài khoản.')

class Login(BaseModel): user:str; password:str=Field(alias='pass')
class Doc(BaseModel): no:str; title:str; date:str=''; due:str=''; secret:str='Thường'; status:str='Chưa thực hiện'
class Task(BaseModel): title:str; time:str=''; status:str='Chưa thực hiện'
class Account(BaseModel): user:str; name:str; password:str=Field(alias='pass'); role:str='Người dùng'
class Settings(BaseModel): reminder_minutes:int=60; overdue:bool=True; screen_notify:bool=True; sound_notify:bool=True; voice_notify:bool=True

@app.get('/healthz')
def healthz():
    c=DB(); c.execute('SELECT 1').fetchone(); c.close(); return {'ok':True,'database':'postgres' if USE_PG else 'sqlite'}

@app.post('/api/login')
def login(x:Login):
    c=DB(); u=c.execute('SELECT * FROM users WHERE user_name=?',(x.user,)).fetchone(); c.close()
    if not u or not u['active'] or not vp(x.password,u['password']): raise HTTPException(401,'Sai tài khoản, mật khẩu hoặc tài khoản đã bị khóa.')
    r=JSONResponse({'id':u['id'],'user':u['user_name'],'name':u['name'],'role':u['role']})
    r.set_cookie(COOKIE,tok(u['id']),httponly=True,samesite='lax',secure=COOKIE_SECURE,max_age=86400); return r

@app.post('/api/logout')
def logout(): r=JSONResponse({'ok':True}); r.delete_cookie(COOKIE); return r

@app.get('/api/me')
def getme(request:Request): return me(request)

def getrows(table,user):
    user_only(user); c=DB(); order='due' if table=='docs' else 'time'; rows=[dict(x) for x in c.execute(f"SELECT * FROM {table} WHERE owner_id=? ORDER BY COALESCE({order},'9999')",(user['id'],)).fetchall()]; c.close(); return rows
@app.get('/api/docs')
def docs(request:Request): return getrows('docs',me(request))
@app.get('/api/tasks')
def tasks(request:Request): return getrows('tasks',me(request))

def addrec(request,x,table):
    user=me(request); user_only(user); c=DB(); now=now_iso()
    if table=='docs': cur=c.execute('INSERT INTO docs(owner_id,date,no,title,due,secret,status,created_at) VALUES(?,?,?,?,?,?,?,?) RETURNING id',(user['id'],x.date,x.no,x.title,x.due,x.secret,x.status,now))
    else: cur=c.execute('INSERT INTO tasks(owner_id,title,time,status,created_at) VALUES(?,?,?,?,?) RETURNING id',(user['id'],x.title,x.time,x.status,now))
    new_id=cur.fetchone()['id']; c.commit(); row=c.execute(f'SELECT * FROM {table} WHERE id=?',(new_id,)).fetchone(); c.close(); return dict(row)
@app.post('/api/docs')
def adddoc(request:Request,x:Doc): return addrec(request,x,'docs')
@app.post('/api/tasks')
def addtask(request:Request,x:Task): return addrec(request,x,'tasks')

def patchrec(request,record_id,x,table):
    user=me(request); user_only(user); c=DB(); old=c.execute(f'SELECT * FROM {table} WHERE id=? AND owner_id=?',(record_id,user['id'])).fetchone()
    if not old: c.close(); raise HTTPException(404,'Không tìm thấy')
    if table=='docs': c.execute('UPDATE docs SET date=?,no=?,title=?,due=?,secret=?,status=? WHERE id=?',(x.date,x.no,x.title,x.due,x.secret,x.status,record_id))
    else: c.execute('UPDATE tasks SET title=?,time=?,status=? WHERE id=?',(x.title,x.time,x.status,record_id))
    c.commit(); row=c.execute(f'SELECT * FROM {table} WHERE id=?',(record_id,)).fetchone(); c.close(); return dict(row)
@app.patch('/api/docs/{id}')
def pdoc(request:Request,id:int,x:Doc): return patchrec(request,id,x,'docs')
@app.patch('/api/tasks/{id}')
def ptask(request:Request,id:int,x:Task): return patchrec(request,id,x,'tasks')

def delrec(request,record_id,table):
    user=me(request); user_only(user); c=DB(); row=c.execute(f'SELECT id FROM {table} WHERE id=? AND owner_id=?',(record_id,user['id'])).fetchone()
    if not row: c.close(); raise HTTPException(404,'Không tìm thấy')
    c.execute(f'DELETE FROM {table} WHERE id=?',(record_id,)); c.commit(); c.close(); return {'ok':True}
@app.delete('/api/docs/{id}')
def ddoc(request:Request,id:int): return delrec(request,id,'docs')
@app.delete('/api/tasks/{id}')
def dtask(request:Request,id:int): return delrec(request,id,'tasks')

@app.get('/api/accounts')
def accounts(request:Request):
    user=me(request); adm(user); c=DB(); rows=[dict(x) for x in c.execute('SELECT id,user_name AS user,name,role,active,created_at FROM users ORDER BY id').fetchall()]; c.close(); return rows
@app.post('/api/accounts')
def addacc(request:Request,x:Account):
    user=me(request); adm(user); c=DB()
    if x.role!='Người dùng': raise HTTPException(400,'Chỉ được tạo tài khoản Người dùng.')
    try: c.execute('INSERT INTO users(user_name,name,password,role,active,created_at) VALUES(?,?,?,?,?,?)',(x.user,x.name,hp(x.password),'Người dùng',True,now_iso())); c.commit()
    except Exception as e:
        c.close()
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower(): raise HTTPException(400,'Tên đăng nhập đã tồn tại')
        raise
    c.close(); return {'ok':True}
@app.patch('/api/accounts/{id}')
def toggle(request:Request,id:int):
    user=me(request); adm(user); c=DB(); a=c.execute('SELECT user_name,active,role FROM users WHERE id=?',(id,)).fetchone()
    if not a or a['user_name']=='NongVanHuy': c.close(); raise HTTPException(400,'Không thể khóa tài khoản quản trị chính')
    c.execute('UPDATE users SET active=? WHERE id=?',(not bool(a['active']),id)); c.commit(); c.close(); return {'ok':True}
@app.delete('/api/accounts/{id}')
def delacc(request:Request,id:int):
    user=me(request); adm(user); c=DB(); a=c.execute('SELECT user_name FROM users WHERE id=?',(id,)).fetchone()
    if not a or a['user_name']=='NongVanHuy': c.close(); raise HTTPException(400,'Không thể xóa quản trị chính')
    c.execute('DELETE FROM users WHERE id=?',(id,)); c.commit(); c.close(); return {'ok':True}

@app.get('/api/settings')
def settings(request:Request):
    user=me(request); user_only(user); c=DB(); s=c.execute('SELECT * FROM settings WHERE user_id=?',(user['id'],)).fetchone()
    if not s:
        c.execute('INSERT INTO settings(user_id) VALUES(?)',(user['id'],)); c.commit(); s=c.execute('SELECT * FROM settings WHERE user_id=?',(user['id'],)).fetchone()
    c.close(); return {'reminder_minutes':s['reminder_minutes'],'overdue':bool(s['overdue']),'screen_notify':bool(s['screen_notify']),'sound_notify':bool(s['sound_notify']),'voice_notify':bool(s['voice_notify'])}
@app.put('/api/settings')
def settings_put(request:Request,x:Settings):
    user=me(request); user_only(user); c=DB()
    if c.pg: c.execute('''INSERT INTO settings(user_id,reminder_minutes,overdue,screen_notify,sound_notify,voice_notify) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET reminder_minutes=EXCLUDED.reminder_minutes,overdue=EXCLUDED.overdue,screen_notify=EXCLUDED.screen_notify,sound_notify=EXCLUDED.sound_notify,voice_notify=EXCLUDED.voice_notify''',(user['id'],x.reminder_minutes,x.overdue,x.screen_notify,x.sound_notify,x.voice_notify))
    else: c.execute('''INSERT INTO settings(user_id,reminder_minutes,overdue,screen_notify,sound_notify,voice_notify) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET reminder_minutes=excluded.reminder_minutes,overdue=excluded.overdue,screen_notify=excluded.screen_notify,sound_notify=excluded.sound_notify,voice_notify=excluded.voice_notify''',(user['id'],x.reminder_minutes,int(x.overdue),int(x.screen_notify),int(x.sound_notify),int(x.voice_notify)))
    c.commit(); c.close(); return {'ok':True}

@app.get('/api/push/public-key')
def push_public_key(request:Request):
    user=me(request); user_only(user)
    if not VAPID_PUBLIC_KEY: raise HTTPException(503,'Chưa cấu hình thông báo đẩy.')
    return {'publicKey':VAPID_PUBLIC_KEY}
@app.post('/api/push/subscribe')
def push_subscribe(request:Request,payload:dict):
    user=me(request); user_only(user); endpoint=payload.get('endpoint'); keys=payload.get('keys',{})
    if not endpoint or not keys.get('p256dh') or not keys.get('auth'): raise HTTPException(400,'Subscription không hợp lệ')
    c=DB()
    if c.pg: c.execute('''INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth,created_at) VALUES(?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET user_id=EXCLUDED.user_id,p256dh=EXCLUDED.p256dh,auth=EXCLUDED.auth''',(user['id'],endpoint,keys['p256dh'],keys['auth'],now_iso()))
    else: c.execute('''INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth,created_at) VALUES(?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id,p256dh=excluded.p256dh,auth=excluded.auth''',(user['id'],endpoint,keys['p256dh'],keys['auth'],now_iso()))
    c.commit(); c.close(); return {'ok':True}
@app.delete('/api/push/subscribe')
def push_unsubscribe(request:Request,payload:dict):
    user=me(request); endpoint=payload.get('endpoint'); c=DB(); c.execute('DELETE FROM push_subscriptions WHERE user_id=? AND endpoint=?',(user['id'],endpoint)); c.commit(); c.close(); return {'ok':True}

def send_web_push(subscription,payload):
    if not (VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY): return False,'VAPID not configured'
    try:
        from pywebpush import webpush
        webpush(subscription_info=subscription,data=json.dumps(payload,ensure_ascii=False),vapid_private_key=VAPID_PRIVATE_KEY,vapid_claims={'sub':VAPID_EMAIL})
        return True,''
    except Exception as e: return False,str(e)

def parse_due(value):
    if not value: return None
    try:
        dt=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=VN_TZ)
        return dt.astimezone(datetime.timezone.utc)
    except Exception: return None

def run_reminders():
    if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY: return {'sent':0,'skipped':'VAPID chưa cấu hình'}
    now=datetime.datetime.now(datetime.timezone.utc); c=DB(); sent=0; removed=0
    users=c.execute("SELECT id FROM users WHERE active=TRUE AND role='Người dùng'").fetchall()
    for u in users:
        uid_=u['id']; s=c.execute('SELECT reminder_minutes,overdue,screen_notify FROM settings WHERE user_id=?',(uid_,)).fetchone(); mins=int(s['reminder_minutes']) if s else 60; overdue=bool(s['overdue']) if s else True; screen=bool(s['screen_notify']) if s else True
        if not screen: continue
        subs=c.execute('SELECT id,endpoint,p256dh,auth FROM push_subscriptions WHERE user_id=?',(uid_,)).fetchall()
        if not subs: continue
        records=[]
        for r in c.execute('SELECT id,title,due,status FROM docs WHERE owner_id=?',(uid_,)).fetchall(): records.append(('Văn bản',r['id'],r['title'],r['due'],r['status']))
        for r in c.execute('SELECT id,title,time,status FROM tasks WHERE owner_id=?',(uid_,)).fetchall(): records.append(('Công việc',r['id'],r['title'],r['time'],r['status']))
        for kind,rid,title,due,status in records:
            if status=='Đã thực hiện': continue
            dt=parse_due(due)
            if not dt: continue
            diff=(dt-now).total_seconds(); ntype='upcoming' if 0<=diff<=mins*60 else ('overdue' if diff<0 and overdue else None)
            if not ntype: continue
            duekey=dt.isoformat(); exists=c.execute('SELECT id FROM notification_log WHERE user_id=? AND kind=? AND record_id=? AND notification_type=? AND due_at=? AND reminder_minutes=?',(uid_,kind,rid,ntype,duekey,mins)).fetchone()
            if exists: continue
            payload={'title':'Nhắc hạn' if ntype=='upcoming' else 'Cảnh báo quá hạn','body':f'{kind} {"sắp đến hạn" if ntype=="upcoming" else "đã quá hạn"}: {title}','type':ntype,'url':'/'}; any_ok=False
            for sub in subs:
                ok,err=send_web_push({'endpoint':sub['endpoint'],'keys':{'p256dh':sub['p256dh'],'auth':sub['auth']}},payload)
                if ok: any_ok=True
                elif '404' in err or '410' in err: c.execute('DELETE FROM push_subscriptions WHERE id=?',(sub['id'],)); removed+=1
            if any_ok:
                c.execute('INSERT INTO notification_log(user_id,kind,record_id,notification_type,due_at,reminder_minutes,sent_at) VALUES(?,?,?,?,?,?,?)',(uid_,kind,rid,ntype,duekey,mins,now.isoformat())); sent+=1
    c.commit(); c.close(); return {'sent':sent,'removed':removed}

@app.post('/api/internal/run-reminders')
def internal_run(request:Request):
    secret=request.headers.get('X-Reminder-Secret',''); expected=os.getenv('REMINDER_SECRET','')
    if not expected or not hmac.compare_digest(secret,expected): raise HTTPException(403,'Không được phép')
    return run_reminders()

app.mount('/',StaticFiles(directory=BASE/'public',html=True),name='public')
