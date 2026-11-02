import asyncio
import errno
import ipaddress
import json
import threading
from flask import jsonify,request,render_template,session

PROBES=[80,443,22,445,8080,3389]

def normalize(value):
    if isinstance(value,str) and '-' in value:
        a,b=value.strip().split('-',1)
        if '.' not in b: b=a.rsplit('.',1)[0]+'.'+b
        first,last=ipaddress.IPv4Address(a),ipaddress.IPv4Address(b)
        if int(first)%256==0 and int(last)-int(first)==255:
            return str(ipaddress.IPv4Network(str(first)+'/24'))
    return value

async def probe_host(ip):
    for port in PROBES:
        writer=None
        try:
            _,writer=await asyncio.wait_for(asyncio.open_connection(ip,port),0.7)
            return {'port':port,'evidence':'tcp_open'}
        except asyncio.TimeoutError: pass
        except OSError as exc:
            if exc.errno==errno.ECONNREFUSED:
                return {'port':port,'evidence':'tcp_refused'}
            if exc.errno not in (errno.ETIMEDOUT,errno.EHOSTUNREACH,errno.ENETUNREACH,errno.ECONNRESET,errno.EACCES): raise
        finally:
            if writer:
                writer.close()
                try: await asyncio.wait_for(writer.wait_closed(),0.2)
                except (OSError,asyncio.TimeoutError): pass
    return None

def install(app,core):
    stop=threading.Event(); state_lock=threading.Lock()
    state=dict(running=False,done=0,total=0,found=0,error=None,run_id=None,targets=[])
    with core.db(True) as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS discovery_runs(id INTEGER PRIMARY KEY,started TEXT,finished TEXT,range_text TEXT,targets TEXT,state TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS discovery_hosts(ip TEXT PRIMARY KEY,first_seen TEXT,last_seen TEXT,last_checked TEXT,last_run INTEGER,evidence TEXT,probe_port INTEGER);
CREATE TABLE IF NOT EXISTS discovery_checks(run_id INTEGER,ip TEXT,responded INTEGER,checked TEXT,evidence TEXT,probe_port INTEGER,PRIMARY KEY(run_id,ip));''')
        c.execute("UPDATE discovery_runs SET state='interrupted',finished=? WHERE state='running'",(core.stamp(),))
    async def perform(hosts,run_id):
        iterator=iter(hosts)
        async def worker():
            while not stop.is_set():
                try: ip=next(iterator)
                except StopIteration: return
                evidence=await probe_host(ip); seen=core.stamp()
                with core.db(True) as c:
                    c.execute('INSERT INTO discovery_checks VALUES(?,?,?,?,?,?)',(run_id,ip,int(bool(evidence)),seen,evidence['evidence'] if evidence else '',evidence['port'] if evidence else None))
                    if evidence:
                        c.execute('INSERT INTO discovery_hosts VALUES(?,?,?,?,?,?,?) ON CONFLICT(ip) DO UPDATE SET last_seen=excluded.last_seen,last_checked=excluded.last_checked,last_run=excluded.last_run,evidence=excluded.evidence,probe_port=excluded.probe_port',(ip,seen,seen,seen,run_id,evidence['evidence'],evidence['port']))
                    else:
                        c.execute('UPDATE discovery_hosts SET last_checked=?,last_run=? WHERE ip=?',(seen,run_id,ip))
                with state_lock:
                    state['done']+=1
                    if evidence: state['found']+=1
        tasks=[asyncio.create_task(worker()) for _ in range(min(32,len(hosts)))]
        pending=set(tasks)
        try:
            while pending:
                done,pending=await asyncio.wait(pending,timeout=.1,return_when=asyncio.FIRST_COMPLETED)
                for task in done: task.result()
                if stop.is_set(): break
        finally:
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
    def run(hosts,run_id):
        error=None
        try: asyncio.run(perform(hosts,run_id))
        except Exception as exc:
            error=str(exc);core.log.exception('Discovery failed')
        finally:
            try:
                with core.db(True) as c:
                    c.execute('UPDATE discovery_runs SET finished=?,state=?,error=? WHERE id=?',(core.stamp(),'error' if error else 'cancelled' if stop.is_set() else 'done',error,run_id))
            except Exception as exc:
                error=error or str(exc);core.log.exception('Discovery finalization failed')
            finally:
                with state_lock: state.update(running=False,error=error)
                core.scan_lock.release()
    @app.get('/discovery')
    def discovery_page():
        return render_template('discovery.html',csrf=session['csrf'],config=core.settings())
    @app.get('/api/discovery')
    def discovery_status():
        with state_lock: result=dict(state)
        with core.db() as c:
            latest=c.execute('SELECT * FROM discovery_runs ORDER BY id DESC LIMIT 1').fetchone()
            result['latest']=dict(latest) if latest else None
            result['checks']=[dict(r) for r in c.execute('SELECT * FROM discovery_checks WHERE run_id=?',(latest['id'],))] if latest else []
        if not result['running'] and latest: result['targets']=json.loads(latest['targets'])
        return jsonify(result)
    @app.get('/api/discovery/hosts')
    def discovery_hosts():
        with core.db() as c:
            latest=c.execute('SELECT id FROM discovery_runs ORDER BY id DESC LIMIT 1').fetchone()
            rows=[dict(r) for r in c.execute("SELECT d.*,h.name,h.tags,h.notes FROM discovery_hosts d LEFT JOIN hosts h ON h.ip=d.ip")]
            checks={r['ip']:r['responded'] for r in c.execute('SELECT ip,responded FROM discovery_checks WHERE run_id=?',(latest['id'],))} if latest else {}
        for row in rows:
            row['response']='responded' if checks.get(row['ip'])==1 else 'no_response' if checks.get(row['ip'])==0 else 'not_checked'
        return jsonify(sorted(rows,key=lambda r:int(ipaddress.IPv4Address(r['ip']))))
    @app.post('/api/discovery')
    def discovery_start():
        try:
            data=request.get_json(); raw=data.get('targets','192.168.178.0-255')
            hosts=core.parse_targets(normalize(raw))
        except (ValueError,TypeError,AttributeError,OSError) as exc: return jsonify(error=str(exc)),400
        if not core.scan_lock.acquire(False): return jsonify(error='Ein Portscan oder Discovery-Lauf ist bereits aktiv'),409
        run_id=None
        try:
            with core.db(True) as c:
                run_id=c.execute("INSERT INTO discovery_runs(started,range_text,targets,state) VALUES(?,?,?,'running')",(core.stamp(),raw,json.dumps(hosts))).lastrowid
            stop.clear()
            with state_lock: state.update(running=True,done=0,total=len(hosts),found=0,error=None,run_id=run_id,targets=hosts)
            threading.Thread(target=run,args=(hosts,run_id),daemon=True).start()
            return jsonify(run_id=run_id),202
        except Exception:
            core.log.exception('Discovery start failed')
            try:
                if run_id:
                    with core.db(True) as c: c.execute("UPDATE discovery_runs SET state='error',finished=?,error='Could not start discovery' WHERE id=?",(core.stamp(),run_id))
            finally:
                with state_lock: state.update(running=False,error='Discovery konnte nicht gestartet werden')
                core.scan_lock.release()
            return jsonify(error='Discovery konnte nicht gestartet werden'),500
    @app.post('/api/discovery/stop')
    def discovery_stop():
        stop.set();return jsonify(ok=True)
