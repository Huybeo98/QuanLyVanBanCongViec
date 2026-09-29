import os,sqlite3,hashlib,hmac,base64,json,secrets,pathlib,datetime,mimetypes
from fastapi import FastAPI,Request,HTTPException,UploadFile,File
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
BASE=pathlib.Path(__file__).resolve().parent
DATA=BASE/'data'; FILES=DATA/'files'; DATA.mkdir(exist_ok=True); FILES.mkdir(exist_ok=True)
DB=DATA/'app.db'; SECRET=os.getenv('APP_SECRET','change-this-secret-in-production').encode(); COOKIE='qvc_session'
app=FastAPI(title='Quản lý Văn bản & Công việc')
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def hp(p,s=None):
    s=s or secrets.token_bytes(16); return s.hex()+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),s,210000).hex()
def vp(p,v):
    try:
        s,h=v.split(':'); return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),210000).hex(),h)
    except: return False
def tok(uid):
    raw=json.dumps({'uid':uid,'exp':int(datetime.datetime.now(datetime.timezone.utc).timestamp())+86400},separators=(',',':')).encode()
    b=base64.urlsafe_b64encode(raw).decode().rstrip('='); return b+'.'+hmac.new(SECRET,b.encode(),hashlib.sha256).hexdigest()
def uid(t):
    try:
        b,s=t.split('.')
        if not hmac.compare_digest(hmac.new(SECRET,b.encode(),hashlib.sha256).hexdigest(),s): return None
        p=json.loads(base64.urlsafe_b64decode(b+'===')); return int(p['uid']) if p['exp']>=int(datetime.datetime.now(datetime.timezone.utc).timestamp()) else None
    except: return None
def init():
    c=db()
    c.executescript("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,user TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'Người dùng',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,date TEXT,no TEXT,title TEXT,due TEXT,secret TEXT,status TEXT,file_id INTEGER,file_name TEXT,created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,title TEXT,time TEXT,status TEXT,file_id INTEGER,file_name TEXT,created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS settings(user_id INTEGER PRIMARY KEY,reminder_minutes INTEGER DEFAULT 60,overdue INTEGER DEFAULT 1,screen_notify INTEGER DEFAULT 1,sound_notify INTEGER DEFAULT 1,voice_notify INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,kind TEXT,record_id INTEGER,name TEXT,path TEXT,created_at TEXT NOT NULL);")
    if not c.execute("SELECT 1 FROM users WHERE user='NongVanHuy'").fetchone():
        c.execute('INSERT INTO users(user,name,password,role,active,created_at) VALUES(?,?,?,?,1,?)',('NongVanHuy','Quản trị viên',hp('11011998Huy@'),'Quản trị',datetime.datetime.now().isoformat()))
    c.commit(); c.close()
init()
def me(request):
    i=uid(request.cookies.get(COOKIE,''))
    if not i: raise HTTPException(401,'Chưa đăng nhập')
    c=db(); u=c.execute('SELECT id,user,name,role,active FROM users WHERE id=?',(i,)).fetchone(); c.close()
    if not u or not u['active']: raise HTTPException(401,'Tài khoản không hợp lệ')
    return dict(u)
def adm(u):
    if u['role']!='Quản trị': raise HTTPException(403,'Chỉ quản trị viên được phép thực hiện')
class Login(BaseModel): user:str; password:str=Field(alias='pass')
class Doc(BaseModel): owner_id:int|None=None; date:str=''; no:str; title:str; due:str=''; secret:str='Thường'; status:str='Chưa thực hiện'
class Task(BaseModel): owner_id:int|None=None; title:str; time:str=''; status:str='Chưa thực hiện'
class Account(BaseModel): user:str; name:str; password:str=Field(alias='pass'); role:str='Người dùng'
class Settings(BaseModel): reminder_minutes:int=60; overdue:bool=True; screen_notify:bool=True; sound_notify:bool=True; voice_notify:bool=True
@app.post('/api/login')
def login(x:Login):
    c=db(); u=c.execute('SELECT * FROM users WHERE user=?',(x.user,)).fetchone(); c.close()
    if not u or not u['active'] or not vp(x.password,u['password']): raise HTTPException(401,'Sai tài khoản, mật khẩu hoặc tài khoản đã bị khóa.')
    r=JSONResponse({'id':u['id'],'user':u['user'],'name':u['name'],'role':u['role']}); r.set_cookie(COOKIE,tok(u['id']),httponly=True,samesite='lax',secure=False,max_age=86400); return r
@app.post('/api/logout')
def logout(): r=JSONResponse({'ok':True}); r.delete_cookie(COOKIE); return r
@app.get('/api/me')
def getme(request:Request): return me(request)
def getrows(table,u):
    c=db(); order='due' if table=='docs' else 'time'; q=f'SELECT t.*,u.user owner_user,u.name owner_name FROM {table} t JOIN users u ON u.id=t.owner_id'; args=()
    if u['role']!='Quản trị': q+=' WHERE t.owner_id=?'; args=(u['id'],)
    q+=f" ORDER BY COALESCE(t.{order},'9999')"; r=[dict(x) for x in c.execute(q,args).fetchall()]; c.close(); return r
@app.get('/api/docs')
def docs(request:Request): return getrows('docs',me(request))
@app.get('/api/tasks')
def tasks(request:Request): return getrows('tasks',me(request))
def addrec(request,x,table):
    u=me(request); oid=x.owner_id if u['role']=='Quản trị' and x.owner_id else u['id']; c=db(); now=datetime.datetime.now().isoformat()
    if table=='docs': cur=c.execute('INSERT INTO docs(owner_id,date,no,title,due,secret,status,created_at) VALUES(?,?,?,?,?,?,?,?)',(oid,x.date,x.no,x.title,x.due,x.secret,x.status,now))
    else: cur=c.execute('INSERT INTO tasks(owner_id,title,time,status,created_at) VALUES(?,?,?,?,?)',(oid,x.title,x.time,x.status,now))
    c.commit(); r=c.execute(f'SELECT * FROM {table} WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); return dict(r)
@app.post('/api/docs')
def adddoc(request:Request,x:Doc): return addrec(request,x,'docs')
@app.post('/api/tasks')
def addtask(request:Request,x:Task): return addrec(request,x,'tasks')
def patchrec(request,id,x,table):
    u=me(request); c=db(); old=c.execute(f'SELECT * FROM {table} WHERE id=?',(id,)).fetchone()
    if not old or (u['role']!='Quản trị' and old['owner_id']!=u['id']): c.close(); raise HTTPException(404,'Không tìm thấy')
    oid=x.owner_id if u['role']=='Quản trị' and x.owner_id else old['owner_id']
    if table=='docs': c.execute('UPDATE docs SET owner_id=?,date=?,no=?,title=?,due=?,secret=?,status=? WHERE id=?',(oid,x.date,x.no,x.title,x.due,x.secret,x.status,id))
    else: c.execute('UPDATE tasks SET owner_id=?,title=?,time=?,status=? WHERE id=?',(oid,x.title,x.time,x.status,id))
    c.commit(); r=c.execute(f'SELECT * FROM {table} WHERE id=?',(id,)).fetchone(); c.close(); return dict(r)
@app.patch('/api/docs/{id}')
def pdoc(request:Request,id:int,x:Doc): return patchrec(request,id,x,'docs')
@app.patch('/api/tasks/{id}')
def ptask(request:Request,id:int,x:Task): return patchrec(request,id,x,'tasks')
def delrec(request,id,table):
    u=me(request); c=db(); o=c.execute(f'SELECT owner_id FROM {table} WHERE id=?',(id,)).fetchone()
    if not o or (u['role']!='Quản trị' and o['owner_id']!=u['id']): c.close(); raise HTTPException(404,'Không tìm thấy')
    c.execute(f'DELETE FROM {table} WHERE id=?',(id,)); c.commit(); c.close(); return {'ok':True}
@app.delete('/api/docs/{id}')
def ddoc(request:Request,id:int): return delrec(request,id,'docs')
@app.delete('/api/tasks/{id}')
def dtask(request:Request,id:int): return delrec(request,id,'tasks')
@app.get('/api/accounts')
def accounts(request:Request):
    u=me(request); adm(u); c=db(); r=[dict(x) for x in c.execute('SELECT id,user,name,role,active,created_at FROM users ORDER BY id').fetchall()]; c.close(); return r
@app.post('/api/accounts')
def addacc(request:Request,x:Account):
    u=me(request); adm(u); c=db()
    try: c.execute('INSERT INTO users(user,name,password,role,active,created_at) VALUES(?,?,?,?,1,?)',(x.user,x.name,hp(x.password),x.role,datetime.datetime.now().isoformat())); c.commit()
    except sqlite3.IntegrityError: c.close(); raise HTTPException(400,'Tên đăng nhập đã tồn tại')
    c.close(); return {'ok':True}
@app.patch('/api/accounts/{id}')
def toggle(request:Request,id:int):
    u=me(request); adm(u); c=db(); a=c.execute('SELECT user,active FROM users WHERE id=?',(id,)).fetchone()
    if not a or a['user']=='NongVanHuy': c.close(); raise HTTPException(400,'Không thể khóa tài khoản quản trị chính')
    c.execute('UPDATE users SET active=? WHERE id=?',(0 if a['active'] else 1,id)); c.commit(); c.close(); return {'ok':True}
@app.delete('/api/accounts/{id}')
def delacc(request:Request,id:int):
    u=me(request); adm(u); c=db(); a=c.execute('SELECT user FROM users WHERE id=?',(id,)).fetchone()
    if not a or a['user']=='NongVanHuy': c.close(); raise HTTPException(400,'Không thể xóa quản trị chính')
    for t,col in [('files','owner_id'),('docs','owner_id'),('tasks','owner_id'),('settings','user_id')]: c.execute(f'DELETE FROM {t} WHERE {col}=?',(id,))
    c.execute('DELETE FROM users WHERE id=?',(id,)); c.commit(); c.close(); return {'ok':True}
@app.get('/api/settings')
def settings(request:Request):
    u=me(request); c=db(); s=c.execute('SELECT * FROM settings WHERE user_id=?',(u['id'],)).fetchone()
    if not s: c.execute('INSERT INTO settings(user_id) VALUES(?)',(u['id'],)); c.commit(); s=c.execute('SELECT * FROM settings WHERE user_id=?',(u['id'],)).fetchone()
    c.close(); return {'reminder_minutes':s['reminder_minutes'],'overdue':bool(s['overdue']),'screen_notify':bool(s['screen_notify']),'sound_notify':bool(s['sound_notify']),'voice_notify':bool(s['voice_notify'])}
@app.put('/api/settings')
def settings_put(request:Request,x:Settings):
    u=me(request); c=db(); c.execute('INSERT INTO settings(user_id,reminder_minutes,overdue,screen_notify,sound_notify,voice_notify) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET reminder_minutes=excluded.reminder_minutes,overdue=excluded.overdue,screen_notify=excluded.screen_notify,sound_notify=excluded.sound_notify,voice_notify=excluded.voice_notify',(u['id'],x.reminder_minutes,int(x.overdue),int(x.screen_notify),int(x.sound_notify),int(x.voice_notify))); c.commit(); c.close(); return {'ok':True}
async def up(kind,id,file,request):
    u=me(request); table='docs' if kind=='docs' else 'tasks'; c=db(); o=c.execute(f'SELECT owner_id FROM {table} WHERE id=?',(id,)).fetchone()
    if not o or (u['role']!='Quản trị' and o['owner_id']!=u['id']): c.close(); raise HTTPException(404,'Không tìm thấy')
    owner=o['owner_id']; ext=pathlib.Path(file.filename or '').suffix; path=FILES/f'{owner}_{kind}_{id}_{secrets.token_hex(8)}{ext}'; path.write_bytes(await file.read()); cur=c.execute('INSERT INTO files(owner_id,kind,record_id,name,path,created_at) VALUES(?,?,?,?,?,?)',(owner,kind,id,file.filename,path.as_posix(),datetime.datetime.now().isoformat())); c.execute(f'UPDATE {table} SET file_id=?,file_name=? WHERE id=?',(cur.lastrowid,file.filename,id)); c.commit(); c.close(); return {'ok':True,'file_id':cur.lastrowid}
@app.post('/api/docs/{id}/file')
async def udf(request:Request,id:int,file:UploadFile=File(...)): return await up('docs',id,file,request)
@app.post('/api/tasks/{id}/file')
async def utf(request:Request,id:int,file:UploadFile=File(...)): return await up('tasks',id,file,request)
@app.get('/api/files/{id}')
def gf(request:Request,id:int):
    u=me(request); c=db(); f=c.execute('SELECT * FROM files WHERE id=?',(id,)).fetchone(); c.close()
    if not f or (u['role']!='Quản trị' and f['owner_id']!=u['id']): raise HTTPException(404,'Không tìm thấy')
    return FileResponse(f['path'],filename=f['name'],media_type=mimetypes.guess_type(f['name'])[0] or 'application/octet-stream')
app.mount('/',StaticFiles(directory=BASE/'public',html=True),name='public')
