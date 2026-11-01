import asyncio
import csv
import errno
import io
import ipaddress
import json
import logging
import math
import os
import secrets
import socket
import sqlite3
import ssl
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from flask import Flask, jsonify, redirect, render_template, request, session, Response
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('lanscan')
VERSION = '1.0.0'
password = os.environ['ADMIN_PASSWORD']
secret = os.environ['SECRET_KEY']
if len(password) < 1 or password.startswith('replace-with') or len(secret) < 24 or secret.startswith('replace-with'):
    raise RuntimeError('Set a unique ADMIN_PASSWORD (1+ characters) and random SECRET_KEY (24+ characters)')
DB = os.getenv('DB_PATH', '/data/index.sqlite')
NETWORKS = [ipaddress.IPv4Network(n.strip()) for n in os.getenv('ALLOWED_NETWORKS', '192.168.178.0/24').split(',')]
app = Flask(__name__)
app.secret_key = secret
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16384)
if os.getenv('TRUSTED_HOSTS'):
    app.config['TRUSTED_HOSTS'] = [h.strip() for h in os.environ['TRUSTED_HOSTS'].split(',')]
write_lock = threading.RLock()
scan_lock = threading.Lock()
stop = threading.Event()
state_lock = threading.Lock()
state = dict(running=False, stopping=False, done=0, total=0, found=0, error=None, scan_id=None)
login_lock = threading.Lock()
attempts = []

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

@contextmanager
def db(write=False):
    guard = write_lock if write else threading.RLock()
    with guard:
        conn = sqlite3.connect(DB, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            if write:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

os.makedirs(os.path.dirname(DB) or '.', exist_ok=True)
with db(True) as c:
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''
CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY,data TEXT);
CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY,started TEXT,finished TEXT,targets TEXT,ports TEXT,state TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS services(ip TEXT,port INTEGER,service TEXT,url TEXT,title TEXT,http_status INTEGER,server TEXT,html TEXT,first_seen TEXT,last_seen TEXT,scan_id INTEGER,PRIMARY KEY(ip,port));
CREATE TABLE IF NOT EXISTS observations(scan_id INTEGER,ip TEXT,port INTEGER,seen TEXT,PRIMARY KEY(scan_id,ip,port));
CREATE TABLE IF NOT EXISTS hosts(ip TEXT PRIMARY KEY,name TEXT DEFAULT '',tags TEXT DEFAULT '',notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS scope(scan_id INTEGER,ip TEXT,PRIMARY KEY(scan_id,ip));
CREATE TABLE IF NOT EXISTS credentials(id INTEGER PRIMARY KEY,hash TEXT,revision INTEGER);
CREATE INDEX IF NOT EXISTS observations_host_port ON observations(ip,port,scan_id);
''')
    c.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (json.dumps(dict(targets='192.168.178.1',ports='1-65535',timeout=0.7,workers=128,http=True,theme='ocean')),))
    c.execute('INSERT OR IGNORE INTO credentials VALUES(1,?,1)', (generate_password_hash(password),))
    c.execute("UPDATE scans SET state='interrupted',finished=?,error='Process restarted' WHERE state='running'", (stamp(),))

def settings():
    with db() as c:
        return json.loads(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])

def parse_ports(text):
    if not isinstance(text, str) or len(text)>2048:
        raise ValueError('Ungültige Portauswahl')
    result=set()
    for token in text.split(','):
        bounds=token.strip().split('-')
        if len(bounds)>2:
            raise ValueError('Ungültige Ports')
        a,b=int(bounds[0]),int(bounds[-1])
        if not 1<=a<=b<=65535:
            raise ValueError('Ports müssen zwischen 1 und 65535 liegen')
        result.update(range(a,b+1))
    return sorted(result)

def parse_targets(text):
    if not isinstance(text,str) or len(text)>4096:
        raise ValueError('Ungültige Ziele')
    result=set()
    for token in text.replace(',',' ').split():
        if '/' in token:
            net=ipaddress.IPv4Network(token,strict=False)
            if net.num_addresses>256:
                raise ValueError('Maximal 256 Adressen pro Netz')
            values=net.hosts()
        elif '-' in token and token[0].isdigit():
            a,b=token.split('-',1)
            if '.' not in b:
                b=a.rsplit('.',1)[0]+'.'+b
            a,b=int(ipaddress.IPv4Address(a)),int(ipaddress.IPv4Address(b))
            if not 0<=b-a<256:
                raise ValueError('Ungültige oder zu große Range')
            values=(ipaddress.IPv4Address(i) for i in range(a,b+1))
        else:
            values={ipaddress.IPv4Address(v[4][0]) for v in socket.getaddrinfo(token,None,socket.AF_INET,socket.SOCK_STREAM)}
        for ip in values:
            if not any(ip in net for net in NETWORKS):
                raise ValueError(f'{ip} außerhalb ALLOWED_NETWORKS')
            result.add(str(ip))
        if len(result)>256:
            raise ValueError('Maximal 256 Hosts')
    if not result:
        raise ValueError('Keine Ziele')
    return sorted(result,key=ipaddress.IPv4Address)

class Title(HTMLParser):
    def __init__(self):
        super().__init__(); self.active=False; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='title': self.active=True
    def handle_endtag(self,tag):
        if tag=='title': self.active=False
    def handle_data(self,data):
        if self.active: self.parts.append(data)

async def close_writer(writer):
    if writer:
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(),0.3)
        except (OSError,asyncio.TimeoutError):
            pass

async def tcp_open(ip,port,timeout):
    writer=None
    try:
        _,writer=await asyncio.wait_for(asyncio.open_connection(ip,port),timeout)
        return True
    except asyncio.TimeoutError:
        return False
    except OSError as exc:
        if exc.errno in (errno.ECONNREFUSED,errno.ETIMEDOUT,errno.EHOSTUNREACH,errno.ENETUNREACH,errno.ECONNRESET,errno.EACCES):
            return False
        raise
    finally:
        await close_writer(writer)

async def http_probe(ip,port,tls):
    writer=None
    try:
        context=None
        if tls:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname=False; context.verify_mode=ssl.CERT_NONE
        reader,writer=await asyncio.open_connection(ip,port,ssl=context)
        writer.write(f'GET / HTTP/1.0\r\nHost: {ip}:{port}\r\nUser-Agent: hAI.LANSCAN/1.0\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n'.encode())
        await writer.drain()
        data=bytearray()
        while len(data)<65536:
            chunk=await reader.read(min(8192,65536-len(data)))
            if not chunk: break
            data.extend(chunk)
        if not data.startswith(b'HTTP/'):
            raise ValueError('Kein HTTP')
        head,_,body=bytes(data).partition(b'\r\n\r\n')
        lines=head.decode('latin1').split('\r\n'); headers={}
        for line in lines[1:]:
            if ':' in line:
                k,v=line.split(':',1); headers[k.lower()]=v.strip()
        html=body.decode('utf-8',errors='replace'); title=Title(); title.feed(html)
        return (f"{'https' if tls else 'http'}://{ip}:{port}/",' '.join(' '.join(title.parts).split())[:500],int(lines[0].split()[1]),headers.get('server',''),html)
    finally:
        await close_writer(writer)

def save_open(scan_id,ip,port):
    seen=stamp()
    try: service=socket.getservbyport(port,'tcp')
    except OSError: service='unknown'
    with db(True) as c:
        c.execute("INSERT OR IGNORE INTO hosts(ip) VALUES(?)",(ip,))
        c.execute("INSERT INTO services(ip,port,service,url,title,server,html,first_seen,last_seen,scan_id) VALUES(?,?,?,'','','','',?,?,?) ON CONFLICT(ip,port) DO UPDATE SET service=excluded.service,last_seen=excluded.last_seen,scan_id=excluded.scan_id",(ip,port,service,seen,seen,scan_id))
        c.execute('INSERT INTO observations VALUES(?,?,?,?)',(scan_id,ip,port,seen))

def save_web(ip,port,meta):
    with db(True) as c:
        c.execute('UPDATE services SET url=?,title=?,http_status=?,server=?,html=? WHERE ip=? AND port=?',(*meta,ip,port))

async def perform(hosts,ports,config,scan_id):
    pairs=iter((ip,port) for ip in hosts for port in ports)
    async def worker():
        while not stop.is_set():
            try: ip,port=next(pairs)
            except StopIteration: return
            if await tcp_open(ip,port,config['timeout']):
                save_open(scan_id,ip,port)
                with state_lock: state['found']+=1
                if config['http'] and not stop.is_set():
                    for tls in ([True,False] if port in (443,8443,9443) else [False,True]):
                        if stop.is_set(): break
                        try:
                            meta=await asyncio.wait_for(http_probe(ip,port,tls),2.5)
                        except (OSError,ValueError,asyncio.TimeoutError):
                            continue
                        save_web(ip,port,meta)
                        break
            with state_lock: state['done']+=1
    tasks=[asyncio.create_task(worker()) for _ in range(config['workers'])]
    pending=set(tasks)
    try:
        while pending:
            done,pending=await asyncio.wait(pending,timeout=0.1,return_when=asyncio.FIRST_COMPLETED)
            for task in done: task.result()
            if stop.is_set(): break
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)

def run(hosts,ports,config,scan_id):
    error=None
    try:
        asyncio.run(perform(hosts,ports,config,scan_id))
    except Exception as exc:
        error=str(exc); log.exception('Scan %s failed',scan_id)
    finally:
        try:
            with db(True) as c:
                c.execute('UPDATE scans SET finished=?,state=?,error=? WHERE id=?',(stamp(),'error' if error else ('cancelled' if stop.is_set() else 'done'),error,scan_id))
        except Exception as exc:
            error=error or str(exc); log.exception('Could not finalize scan %s',scan_id)
        finally:
            with state_lock:
                state.update(running=False,stopping=False,error=error)
            scan_lock.release()

def inventory_rows():
    with db() as c:
        services=[dict(r) for r in c.execute('SELECT s.ip,s.port,s.service,s.url,s.title,s.http_status,s.server,s.first_seen,s.last_seen,s.scan_id,h.name,h.tags,h.notes FROM services s LEFT JOIN hosts h ON h.ip=s.ip')]
        latest=c.execute('SELECT id,state FROM scans ORDER BY id DESC LIMIT 1').fetchone()
        completed=[dict(r) for r in c.execute("SELECT id,ports FROM scans WHERE state='done' ORDER BY id DESC")]
        scope={}
        for r in c.execute('SELECT scan_id,ip FROM scope'):
            scope.setdefault(r['scan_id'],set()).add(r['ip'])
        observations={}
        counts={}
        for r in c.execute('SELECT scan_id,ip,port FROM observations'):
            observations.setdefault(r['scan_id'],set()).add((r['ip'],r['port']))
            key=(r['ip'],r['port']); counts[key]=counts.get(key,0)+1
    portsets={r['id']:set(parse_ports(r['ports'])) for r in completed}
    for row in services:
        ip,port=row['ip'],row['port']; relevant=[r for r in completed if ip in scope.get(r['id'],set()) and port in portsets[r['id']]]
        row['status']='historical'; row['change']='unknown'
        if relevant:
            current=relevant[0]['id']; found=(ip,port) in observations.get(current,set())
            row['status']='open' if found else 'not_found'
            if len(relevant)>1:
                before=(ip,port) in observations.get(relevant[1]['id'],set())
                row['change']='returned' if found and not before else ('missing' if before and not found else 'unchanged')
            elif found: row['change']='new'
        if latest:
            if row['scan_id']==latest['id'] and latest['state']!='done': row['status']='observed_partial'
            elif ip not in scope.get(latest['id'],set()): row['status']='not_checked'
            else:
                with db() as c: selected=c.execute('SELECT ports FROM scans WHERE id=?',(latest['id'],)).fetchone()[0]
                if port not in set(parse_ports(selected)): row['status']='not_checked'
        row['new']=counts.get((ip,port),0)==1
    return sorted(services,key=lambda r:(int(ipaddress.IPv4Address(r['ip'])),r['port']))

@app.before_request
def protect():
    if request.endpoint in ('login','health'): return
    if not session.get('authenticated'):
        return (jsonify(error='Anmeldung erforderlich'),401) if request.path.startswith('/api/') else redirect('/login')
    with db() as c: revision=c.execute('SELECT revision FROM credentials WHERE id=1').fetchone()[0]
    if session.get('revision')!=revision:
        session.clear(); return jsonify(error='Bitte erneut anmelden'),401
    if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf',request.headers.get('X-CSRF-Token','')),session.get('csrf','invalid')):
        return jsonify(error='CSRF-Prüfung fehlgeschlagen'),403

@app.after_request
def secure_headers(response):
    response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
    return response

@app.get('/healthz')
def health():
    try:
        with db() as c: c.execute('SELECT 1 FROM settings').fetchone()
        return jsonify(ok=True,version=VERSION)
    except sqlite3.Error:
        return jsonify(ok=False),503

@app.route('/login',methods=['GET','POST'])
def login():
    session.setdefault('csrf',secrets.token_urlsafe(32)); error=None
    if request.method=='POST':
        if not secrets.compare_digest(request.form.get('csrf',''),session['csrf']): return 'CSRF',403
        with login_lock:
            now=time.monotonic(); attempts[:]=[t for t in attempts if now-t<300]
            if len(attempts)>=10: return 'Zu viele Versuche, fünf Minuten warten',429
            attempts.append(now)
        with db() as c: credential=c.execute('SELECT * FROM credentials WHERE id=1').fetchone()
        if check_password_hash(credential['hash'],request.form.get('password','')):
            session.clear(); session.update(authenticated=True,revision=credential['revision'],csrf=secrets.token_urlsafe(32)); session.permanent=True
            return redirect('/')
        error='Passwort falsch'
    return render_template('v1.html',login=True,error=error,csrf=session['csrf'])

@app.post('/logout')
def logout():
    session.clear(); return redirect('/login')

@app.get('/')
def index():
    return render_template('v1.html',login=False,config=settings(),csrf=session['csrf'])

@app.get('/api/status')
def get_status():
    with state_lock: return jsonify(state)

@app.get('/api/services')
def inventory():
    return jsonify(inventory_rows())

@app.get('/api/scans')
def history():
    with db() as c: return jsonify([dict(r) for r in c.execute('SELECT * FROM scans ORDER BY id DESC LIMIT 100')])

@app.post('/api/scan')
def start():
    if not scan_lock.acquire(False): return jsonify(error='Ein Scan läuft bereits'),409
    scan_id=None
    try:
        data=request.get_json(); hosts=parse_targets(data['targets']); ports=parse_ports(data['ports']); config=settings()
        with db(True) as c:
            scan_id=c.execute("INSERT INTO scans(started,targets,ports,state) VALUES(?,?,?,'running')",(stamp(),data['targets'],data['ports'])).lastrowid
            c.executemany('INSERT INTO scope VALUES(?,?)',[(scan_id,ip) for ip in hosts])
        stop.clear()
        with state_lock: state.update(running=True,stopping=False,done=0,total=len(hosts)*len(ports),found=0,error=None,scan_id=scan_id)
        threading.Thread(target=run,args=(hosts,ports,config,scan_id),daemon=True).start()
        return jsonify(scan_id=scan_id),202
    except (ValueError,KeyError,TypeError,socket.gaierror) as exc:
        scan_lock.release(); return jsonify(error=str(exc)),400
    except Exception:
        with state_lock: state['running']=False
        scan_lock.release(); log.exception('Cannot start scan'); return jsonify(error='Scan konnte nicht gestartet werden'),500

@app.post('/api/stop')
def cancel():
    with state_lock:
        if state['running']: state['stopping']=True; stop.set()
    return jsonify(ok=True)

@app.post('/api/settings')
def save_settings():
    try:
        d=request.get_json(); cfg=dict(targets=str(d['targets']),ports=str(d['ports']),timeout=float(d['timeout']),workers=int(d['workers']),http=d['http'],theme=str(d['theme']))
        if not math.isfinite(cfg['timeout']) or not 0.1<=cfg['timeout']<=10 or not 1<=cfg['workers']<=256 or type(cfg['http']) is not bool or cfg['theme'] not in ('light','dark','ocean'):
            raise ValueError('Ungültige Einstellungen')
        parse_targets(cfg['targets']); parse_ports(cfg['ports'])
        with db(True) as c: c.execute('UPDATE settings SET data=? WHERE id=1',(json.dumps(cfg),))
        return jsonify(ok=True)
    except (KeyError,ValueError,TypeError,socket.gaierror) as exc: return jsonify(error=str(exc)),400

@app.post('/api/host')
def save_host():
    try:
        d=request.get_json(); ip=str(ipaddress.IPv4Address(d['ip']))
        name=str(d.get('name','')).strip(); tags=str(d.get('tags','')).strip(); notes=str(d.get('notes','')).strip()
        if len(name)>120 or len(tags)>500 or len(notes)>4000: raise ValueError('Text zu lang')
        with db(True) as c:
            if not c.execute('SELECT 1 FROM services WHERE ip=?',(ip,)).fetchone(): return jsonify(error='Host nicht im Index'),404
            c.execute('INSERT INTO hosts VALUES(?,?,?,?) ON CONFLICT(ip) DO UPDATE SET name=excluded.name,tags=excluded.tags,notes=excluded.notes',(ip,name,tags,notes))
        return jsonify(ok=True)
    except (ValueError,KeyError,TypeError) as exc: return jsonify(error=str(exc)),400

@app.post('/api/password')
def change_password():
    d=request.get_json(); new=d.get('new','')
    if not isinstance(new,str) or not 1<=len(new)<=256 or new.startswith('replace-with'): return jsonify(error='Neues Passwort: 1 bis 256 Zeichen'),400
    with db(True) as c:
        credential=c.execute('SELECT * FROM credentials WHERE id=1').fetchone()
        if not check_password_hash(credential['hash'],d.get('current','')): return jsonify(error='Bisheriges Passwort falsch'),403
        c.execute('UPDATE credentials SET hash=?,revision=revision+1 WHERE id=1',(generate_password_hash(new),))
    session.clear(); return jsonify(ok=True)

@app.get('/api/export.csv')
def export():
    rows=inventory_rows(); out=io.StringIO(); writer=csv.writer(out)
    fields=['ip','name','tags','port','service','url','title','status','change','first_seen','last_seen']
    writer.writerow(fields)
    for row in rows:
        values=[row.get(k,'') for k in fields]
        writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=lan-index.csv'})
