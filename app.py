import asyncio, csv, io, ipaddress, json, os, secrets, socket, sqlite3, ssl, threading, time
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from flask import Flask, request, session, redirect, render_template, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']
PASSWORD_HASH = generate_password_hash(os.environ['ADMIN_PASSWORD'])
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE')=='true', PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16384)
DB = os.getenv('DB_PATH','/data/index.sqlite')
NETWORKS = [ipaddress.ip_network(n.strip()) for n in os.getenv('ALLOWED_NETWORKS','192.168.178.0/24').split(',')]
scan_lock = threading.Lock()
status = {'running':False,'done':0,'total':0,'found':0,'error':None}
attempts = []
attempt_lock = threading.Lock()
def stamp(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect():
    c=sqlite3.connect(DB, timeout=30); c.row_factory=sqlite3.Row; return c
os.makedirs(os.path.dirname(DB) or '.',exist_ok=True)
with connect() as c:
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY, data TEXT); CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY,started TEXT,finished TEXT,targets TEXT,ports TEXT,state TEXT,error TEXT); CREATE TABLE IF NOT EXISTS services(ip TEXT,port INTEGER,service TEXT,url TEXT,title TEXT,http_status INTEGER,server TEXT,html TEXT,first_seen TEXT,last_seen TEXT,scan_id INTEGER,PRIMARY KEY(ip,port)); CREATE TABLE IF NOT EXISTS observations(scan_id INTEGER,ip TEXT,port INTEGER,seen TEXT,PRIMARY KEY(scan_id,ip,port));')
    c.execute("INSERT OR IGNORE INTO settings VALUES(1,?)",(json.dumps(dict(targets='192.168.178.1',ports='1-65535',timeout=0.7,workers=128,http=True,theme='ocean')),))
    c.execute("UPDATE scans SET state='interrupted' WHERE state='running'")
def settings():
    with connect() as c: return json.loads(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])
def parse_targets(text):
    result=set()
    for token in text.replace(',',' ').split():
        if '/' in token:
            net=ipaddress.IPv4Network(token,strict=False)
            if net.num_addresses>258: raise ValueError('Maximal 256 Hosts')
            values=list(net.hosts())
        elif '-' in token and token[0].isdigit():
            a,b=token.split('-',1)
            if '.' not in b: b=a.rsplit('.',1)[0]+'.'+b
            start,end=int(ipaddress.IPv4Address(a)),int(ipaddress.IPv4Address(b))
            if not 0<=end-start<256: raise ValueError('Range zu groß oder ungültig')
            values=[ipaddress.IPv4Address(n) for n in range(start,end+1)]
        else:
            values=[ipaddress.IPv4Address(a[4][0]) for a in socket.getaddrinfo(token,None,socket.AF_INET,socket.SOCK_STREAM)]
        for ip in values:
            if not any(ip in net for net in NETWORKS): raise ValueError(f'{ip} nicht in ALLOWED_NETWORKS')
            result.add(str(ip))
        if len(result)>256: raise ValueError('Maximal 256 Hosts')
    if not result: raise ValueError('Keine Ziele')
    return sorted(result,key=ipaddress.IPv4Address)
def parse_ports(text):
    result=set()
    for token in text.split(','):
        bounds=token.strip().split('-')
        if len(bounds)>2: raise ValueError('Ungültige Ports')
        a,b=int(bounds[0]),int(bounds[-1])
        if not 1<=a<=b<=65535: raise ValueError('Ports: 1 bis 65535')
        result.update(range(a,b+1))
    return sorted(result)
class Title(HTMLParser):
    def __init__(self): super().__init__(); self.active=False; self.parts=[]
    def handle_starttag(self,t,a):
        if t=='title': self.active=True
    def handle_endtag(self,t):
        if t=='title': self.active=False
    def handle_data(self,d):
        if self.active: self.parts.append(d)
async def probe(ip,port,tls):
    writer=None
    try:
        ctx=None
        if tls:
            ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        reader,writer=await asyncio.open_connection(ip,port,ssl=ctx)
        writer.write(f'GET / HTTP/1.0\r\nHost: {ip}:{port}\r\nUser-Agent: hAI.LANSCAN\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n'.encode()); await writer.drain()
        data=bytearray()
        while len(data)<65536:
            part=await reader.read(min(8192,65536-len(data)))
            if not part: break
            data.extend(part)
        if not data.startswith(b'HTTP/'): raise ValueError('Kein HTTP')
        head,_,body=bytes(data).partition(b'\r\n\r\n'); lines=head.decode('latin1').split('\r\n'); headers={}
        for line in lines[1:]:
            if ':' in line:
                k,v=line.split(':',1); headers[k.lower()]=v.strip()
        html=body.decode('utf-8',errors='replace'); title=Title(); title.feed(html)
        return (f"{'https' if tls else 'http'}://{ip}:{port}/",' '.join(' '.join(title.parts).split())[:500],int(lines[0].split()[1]),headers.get('server',''),html)
    finally:
        if writer: writer.close()
async def perform(hosts,ports,config,scan_id):
    queue=asyncio.Queue(maxsize=config['workers']*2)
    async def worker():
        while True:
            ip,port=await queue.get()
            try:
                _,writer=await asyncio.wait_for(asyncio.open_connection(ip,port),config['timeout']); writer.close()
                try: service=socket.getservbyport(port,'tcp')
                except OSError: service='unknown'
                meta=('', '', None, '', '')
                if config['http']:
                    for tls in ([True,False] if port in (443,8443,9443) else [False,True]):
                        try: meta=await asyncio.wait_for(probe(ip,port,tls),2.5); break
                        except (OSError,ValueError,asyncio.TimeoutError): pass
                seen=stamp()
                with connect() as c:
                    c.execute('INSERT INTO services VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(ip,port) DO UPDATE SET service=excluded.service,url=excluded.url,title=excluded.title,http_status=excluded.http_status,server=excluded.server,html=excluded.html,last_seen=excluded.last_seen,scan_id=excluded.scan_id',(ip,port,service,*meta,seen,seen,scan_id))
                    c.execute('INSERT INTO observations VALUES(?,?,?,?)',(scan_id,ip,port,seen))
                status['found']+=1
            except (OSError,asyncio.TimeoutError): pass
            except Exception as exc: status['error']=str(exc)
            finally: status['done']+=1; queue.task_done()
    workers=[asyncio.create_task(worker()) for _ in range(config['workers'])]
    try:
        for ip in hosts:
            for port in ports: await queue.put((ip,port))
        await queue.join()
    finally:
        for task in workers: task.cancel()
        await asyncio.gather(*workers,return_exceptions=True)
def run(hosts,ports,config,scan_id):
    try: asyncio.run(perform(hosts,ports,config,scan_id))
    except Exception as exc: status['error']=str(exc)
    finally:
        with connect() as c: c.execute('UPDATE scans SET finished=?,state=?,error=? WHERE id=?',(stamp(),'error' if status['error'] else 'done',status['error'],scan_id))
        status['running']=False; scan_lock.release()
@app.before_request
def protect():
    if request.endpoint=='login': return
    if not session.get('authenticated'):
        if request.path.startswith('/api/'): return jsonify(error='Anmeldung erforderlich'),401
        return redirect('/login')
    if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf',request.headers.get('X-CSRF-Token','')),session.get('csrf','invalid')): return 'CSRF-Prüfung fehlgeschlagen',403
@app.after_request
def headers(response):
    response.headers['Cache-Control']='no-store'; response.headers['X-Content-Type-Options']='nosniff'; response.headers['X-Frame-Options']='DENY'; response.headers['Referrer-Policy']='no-referrer'; return response
@app.route('/login',methods=['GET','POST'])
def login():
    session.setdefault('csrf',secrets.token_urlsafe(32)); error=None
    if request.method=='POST':
        if not secrets.compare_digest(request.form.get('csrf',''),session['csrf']): return 'Ungültige Anfrage',403
        with attempt_lock:
            now=time.monotonic(); attempts[:]=[t for t in attempts if now-t<300]
            if len(attempts)>=10: return 'Zu viele Versuche. In fünf Minuten erneut versuchen.',429
            attempts.append(now)
        if check_password_hash(PASSWORD_HASH,request.form.get('password','')):
            session.clear(); session.update(authenticated=True,csrf=secrets.token_urlsafe(32)); session.permanent=True; return redirect('/')
        error='Passwort falsch'
    return render_template('login.html',error=error,csrf=session['csrf'])
@app.post('/logout')
def logout(): session.clear(); return redirect('/login')
@app.get('/')
def index(): return render_template('index.html',config=settings(),csrf=session['csrf'])
@app.get('/api/status')
def get_status(): return jsonify(status)
@app.get('/api/services')
def inventory():
    with connect() as c: return jsonify([dict(r) for r in c.execute('SELECT ip,port,service,url,title,http_status,server,first_seen,last_seen,scan_id FROM services ORDER BY ip,port')])
@app.get('/api/scans')
def history():
    with connect() as c: return jsonify([dict(r) for r in c.execute('SELECT * FROM scans ORDER BY id DESC LIMIT 100')])
@app.get('/api/export.csv')
def export():
    with connect() as c:
        rows=c.execute('SELECT ip,port,service,url,title,http_status,server,first_seen,last_seen FROM services ORDER BY ip,port'); out=io.StringIO(); writer=csv.writer(out); writer.writerow([d[0] for d in rows.description])
        for row in rows:
            writer.writerow([("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for v in row])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=lan-index.csv'})
@app.post('/api/settings')
def save_settings():
    try:
        d=request.get_json(); config=dict(targets=str(d['targets'])[:4096],ports=str(d['ports'])[:2048],timeout=float(d['timeout']),workers=int(d['workers']),http=bool(d['http']),theme=str(d['theme']))
        if not 0.1<=config['timeout']<=10 or not 1<=config['workers']<=256 or config['theme'] not in ('light','dark','ocean'): raise ValueError('Ungültige Einstellungen')
        parse_targets(config['targets']); parse_ports(config['ports'])
        with connect() as c: c.execute('UPDATE settings SET data=? WHERE id=1',(json.dumps(config),))
        return jsonify(ok=True)
    except Exception as exc: return jsonify(error=str(exc)),400
@app.post('/api/scan')
def start():
    if not scan_lock.acquire(False): return jsonify(error='Ein Scan läuft bereits'),409
    try:
        data=request.get_json(); config=settings(); hosts=parse_targets(data['targets']); ports=parse_ports(data['ports'])
        with connect() as c: scan_id=c.execute('INSERT INTO scans(started,targets,ports,state) VALUES(?,?,?,?)',(stamp(),data['targets'],data['ports'],'running')).lastrowid
        status.update(running=True,done=0,total=len(hosts)*len(ports),found=0,error=None)
        threading.Thread(target=run,args=(hosts,ports,config,scan_id),daemon=True).start(); return jsonify(scan_id=scan_id),202
    except Exception as exc: scan_lock.release(); return jsonify(error=str(exc)),400
