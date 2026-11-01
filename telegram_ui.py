import html
import json
import os
import secrets
import time
import urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from integrations import backend,HTTP

LABELS={'done':'✅ Fertig','running':'🔄 Läuft','cancelled':'⏹ Gestoppt','error':'❌ Fehler','interrupted':'⚠️ Unterbrochen'}
def esc(value,limit=160):
    return html.escape(str(value or '')[:limit])
def progress(done,total):
    percent=min(100,max(0,round(done*100/total))) if total else 0
    count=percent//10
    return '🟩'*count+'⬜'*(10-count)+f' {percent}%'
def collect():
    return backend('/api/status'),backend('/api/services'),backend('/api/scans')
def dashboard(title='📡 LAN-Dashboard',snapshot=None):
    state,rows,scans=snapshot or collect()
    host_count=len({r['ip'] for r in rows})
    web_count=sum(bool(r.get('url')) for r in rows)
    recent=0
    cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
    for run in scans:
        try:
            if datetime.fromisoformat(run['started'])>=cutoff: recent+=1
        except (ValueError,TypeError,KeyError): pass
    lines=[f'<b>{esc(title)}</b>','━━━━━━━━━━━━━━━━━━━━',f'🖥 Hosts im Index: <b>{host_count}</b>',f'🔌 Port-Einträge: <b>{len(rows)}</b>',f'🌐 Webdienste: <b>{web_count}</b>',f'🗓 Scanstarts letzte 24 h: <b>{recent}</b> <i>(aus letzten 100 Läufen)</i>','']
    if state.get('running'):
        lines += ['⏳ Scan wird gestoppt' if state.get('stopping') else '🔄 Scan läuft',progress(state.get('done',0),state.get('total',0)),f"Prüfungen: {state.get('done',0)}/{state.get('total',0)} · offen: {state.get('found',0)}"]
    else: lines+=['🟢 Scanner bereit – kein aktiver Scan']
    if state.get('error'): lines+=['⚠️ Letzter Scan meldet einen Fehler – Details in der Webapp.']
    if scans:
        last=scans[0]
        lines += ['',f"🧾 Letzter Lauf #{last['id']}: {LABELS.get(last['state'],esc(last['state']))}",f"🎯 <code>{esc(last.get('targets'))}</code>",f"🕒 Start (UTC): {esc(last.get('started'))}"]
    lines+=['','ℹ️ Historischer Index, keine Live-Onlinezählung.','🔒 Nur freigegebene private Admin-Chats.']
    return '\n'.join(lines)

def run_bot():
    bot=os.environ['TELEGRAM_BOT_TOKEN']
    admins={int(v.strip()) for v in os.environ['TELEGRAM_ADMIN_IDS'].split(',') if v.strip()}
    if not bot or bot.startswith('replace-with') or not admins: raise RuntimeError('Configure TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_IDS')
    zone=ZoneInfo(os.getenv('TELEGRAM_TIMEZONE','Europe/Berlin'))
    hour,minute=map(int,os.getenv('TELEGRAM_REPORT_TIME','08:00').split(':'))
    if not 0<=hour<24 or not 0<=minute<60: raise RuntimeError('TELEGRAM_REPORT_TIME must be HH:MM')
    path=Path(os.getenv('TELEGRAM_STATE_PATH','/botdata/reports.json'))
    path.parent.mkdir(parents=True,exist_ok=True)
    try: reported=json.loads(path.read_text())
    except FileNotFoundError: reported={}
    if not isinstance(reported,dict): raise RuntimeError('Invalid Telegram report state')
    pending={}; watched={}; started=set(); offset=0; next_report=0
    menu=[[('📡 Status','status'),('🗂 Index','index')],[('🌐 Webscan','web'),('🔎 Alle TCP-Ports','full')],[('⏹ Stoppen','stop'),('⚙️ Admin','admin')],[('📊 Zusammenfassung','report')]]
    def api(method,data):
        req=urllib.request.Request('https://api.telegram.org/bot'+bot+'/'+method,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with HTTP.open(req,timeout=35) as response: result=json.load(response)
        if not result.get('ok'): raise RuntimeError('Telegram rejected request')
        return result['result']
    def send(chat,text,buttons=None):
        data={'chat_id':chat,'text':text,'parse_mode':'HTML','link_preview_options':{'is_disabled':True}}
        if buttons: data['reply_markup']={'inline_keyboard':[[{'text':label,'callback_data':action} for label,action in row] for row in buttons]}
        return api('sendMessage',data)
    def persist():
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(reported));temp.replace(path)
    def preview(user,chat,route,data,title):
        now=time.monotonic()
        for key in list(pending):
            if pending[key]['expires']<now: pending.pop(key,None)
        if len(pending)>100: pending.clear()
        key=secrets.token_hex(8)
        pending[key]=dict(user=user,chat=chat,route=route,data=data,expires=now+300)
        body=esc(json.dumps(data,ensure_ascii=False,indent=2),2300)
        send(chat,f'<b>{esc(title)}</b>\n\n<pre>{body}</pre>\n🔐 Einmalige Bestätigung, 5 Minuten gültig.',[[('✅ Ausführen','yes:'+key),('❌ Abbrechen','no:'+key)]])
    def notification_tick():
        nonlocal next_report
        now=datetime.now(zone)
        if time.monotonic()<next_report: return
        next_report=time.monotonic()+60
        try: snapshot=collect()
        except Exception: return
        day=now.date().isoformat()
        due=(now.hour,now.minute)>=(hour,minute)
        for admin in admins:
            if admin not in started:
                try:
                    send(admin,'<b>🚀 hAI.LANSCAN · Bot gestartet</b>\n✅ Verbindung zur Webapp hergestellt.\n\n'+dashboard('📡 Aktueller Stand',snapshot),menu)
                    started.add(admin)
                except Exception: continue
            if due and reported.get(str(admin))!=day:
                try:
                    send(admin,dashboard('📊 Täglicher LAN-Bericht',snapshot)+f'\n🕘 {esc(now.strftime("%d.%m.%Y %H:%M"))} · {esc(str(zone))}',menu)
                    reported[str(admin)]=day; persist()
                except Exception: pass
    while True:
        try:
            notification_tick()
            updates=api('getUpdates',{'offset':offset,'timeout':20,'allowed_updates':['message','callback_query']})
            for update in updates:
                offset=update['update_id']+1
                cb=update.get('callback_query')
                message=cb.get('message',{}) if cb else update.get('message',{})
                user=(cb.get('from',{}) if cb else message.get('from',{})).get('id')
                chat=message.get('chat',{})
                allowed=user in admins and chat.get('type')=='private'
                if cb: api('answerCallbackQuery',{'callback_query_id':cb['id'],'text':'' if allowed else '🔒 Nicht freigegeben'})
                if not allowed: continue
                chat_id=chat['id']; action=cb.get('data','') if cb else message.get('text','')
                try:
                    if action.startswith(('yes:','no:')):
                        prefix,key=action.split(':',1); item=pending.get(key)
                        if not item or item['user']!=user or item['chat']!=chat_id or item['expires']<time.monotonic():
                            send(chat_id,'⌛ Bestätigung abgelaufen oder ungültig.',menu);continue
                        pending.pop(key,None)
                        if prefix=='no': send(chat_id,'❌ Aktion verworfen.',menu);continue
                        result=backend(item['route'],item['data'])
                        if item['route']=='/api/scan':
                            watched[result['scan_id']]=chat_id
                            text=f"🚀 <b>Scan #{result['scan_id']} gestartet</b>\n🎯 <code>{esc(item['data']['targets'])}</code>\n🔌 Ports: <code>{esc(item['data']['ports'])}</code>"
                        elif item['route']=='/api/stop': text='⏹ <b>Scanabbruch angefordert</b>\n💾 Gespeicherte Funde bleiben erhalten.'
                        else: text='✅ <b>Änderung gespeichert</b>'
                        send(chat_id,text,menu)
                    elif action in ('status','/status','report','/report','/start','/menu','home'):
                        send(chat_id,dashboard('📊 LAN-Zusammenfassung' if action in ('report','/report') else '📡 LAN-Dashboard'),menu)
                    elif action in ('index','/index') or action.startswith('/find '):
                        query=action[6:].strip().lower() if action.startswith('/find ') else ''
                        rows=[r for r in backend('/api/services') if query in json.dumps(r,ensure_ascii=False).lower()]
                        lines=['🗂 <b>Dein LAN-Index</b>',f'🔎 {len(rows)} passende Port-Einträge','━━━━━━━━━━━━━━━━━━━━']
                        for row in rows[:10]:
                            icon='🌐' if row.get('url') else '🔌'
                            lines+=[f"{icon} <code>{esc(row['ip'])}:{row['port']}</code> · {esc(row.get('name') or row['service'],70)}"]
                            if row.get('title'): lines+=['   ↳ '+esc(row['title'],90)]
                        if len(rows)>10: lines+=['… Weitere Ergebnisse mit /find TEXT oder in der Webapp.']
                        send(chat_id,'\n'.join(lines),menu)
                    elif action in ('web','full') or action.startswith('/scan '):
                        cfg=backend('/api/settings'); target=cfg['targets']; ports='80,443,8080,8443' if action=='web' else '1-65535'
                        if action.startswith('/scan '):
                            parts=action.split(maxsplit=2);target=parts[1];ports=parts[2] if len(parts)>2 else '80,443,8080,8443'
                        preview(user,chat_id,'/api/scan',dict(targets=target,ports=ports),'🔎 TCP-Scan bestätigen')
                    elif action in ('stop','/stop'): preview(user,chat_id,'/api/stop',{},'⏹ Laufenden Scan stoppen')
                    elif action in ('admin','/admin'):
                        cfg=backend('/api/settings')
                        send(chat_id,'⚙️ <b>Administration</b>\n\n'+f"🎯 Ziel: <code>{esc(cfg['targets'])}</code>\n🔌 Ports: <code>{esc(cfg['ports'])}</code>\n⏱ Timeout: {esc(cfg['timeout'])} s\n⚡ Parallelität: {esc(cfg['workers'])}\n🌐 HTTP-Abfrage: {'✅ an' if cfg['http'] else '⬜ aus'}\n\n🕘 Tagesbericht: {hour:02d}:{minute:02d} {esc(str(zone))}\n\n/name IP NAME\n/scan ZIEL [PORTS]\n/find TEXT\n🔒 Secrets nur in Portainer ändern.",[[('🌐 HTTP umschalten','toggle-http')],[('🏠 Menü','home')]])
                    elif action=='toggle-http':
                        cfg=backend('/api/settings');cfg['http']=not cfg['http']
                        preview(user,chat_id,'/api/settings',cfg,'⚙️ Einstellungen ersetzen / HTTP umschalten')
                    elif action.startswith('/name '):
                        parts=action.split(maxsplit=2)
                        if len(parts)!=3: raise ValueError('Syntax')
                        rows=[r for r in backend('/api/services') if r['ip']==parts[1]]
                        if not rows: raise ValueError('Unknown host')
                        host=rows[0]
                        preview(user,chat_id,'/api/host',dict(ip=parts[1],name=parts[2],tags=host.get('tags') or '',notes=host.get('notes') or ''),'✏️ Hostdaten ersetzen')
                    else: send(chat_id,'👋 <b>hAI.LANSCAN</b>\n📡 /status · 🗂 /index · 📊 /report\n🔎 /scan ZIEL [PORTS]\n✏️ /name IP NAME · 🔍 /find TEXT',menu)
                except Exception: send(chat_id,'⚠️ <b>Aktion fehlgeschlagen</b>\nBitte Backend, Ziel und Portauswahl prüfen. Keine Zugangsdaten in den Chat senden.',menu)
            if watched:
                for record in backend('/api/scans'):
                    ident=record['id']
                    if ident in watched and record['state']!='running':
                        send(watched[ident],f"🧾 <b>Scan #{ident}</b>\n{LABELS.get(record['state'],esc(record['state']))}\n🎯 <code>{esc(record['targets'])}</code>\n💾 Ergebnisse im Index verfügbar.",menu)
                        watched.pop(ident,None)
        except Exception:
            print('Telegram temporarily unavailable; retrying without logging secrets',flush=True);time.sleep(5)

if __name__=='__main__': run_bot()
