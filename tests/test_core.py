import asyncio
import importlib
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
os.environ['ADMIN_PASSWORD']='test-password-only-123'
os.environ['SECRET_KEY']='test-secret-only-not-production-1234567890'
os.environ['ALLOWED_NETWORKS']='192.168.178.0/24'
os.environ['DB_PATH']=os.path.join(tempfile.mkdtemp(),'core.sqlite')
m=importlib.import_module('core')
class Tests(unittest.TestCase):
    def setUp(self):
        m.stop.clear()
        with m.db(True) as c:
            for table in ['services','hosts','scans','scope','observations']:
                c.execute('DELETE FROM '+table)
    def test_validation(self):
        self.assertEqual(m.parse_ports('22,80-82'),[22,80,81,82])
        self.assertEqual(len(m.parse_targets('192.168.178.10-12')),3)
        for value in ['0','65536','80-22']:
            with self.assertRaises(ValueError): m.parse_ports(value)
        with self.assertRaises(ValueError): m.parse_targets('8.8.8.8')
    def test_db_closed(self):
        with m.db() as c: c.execute('SELECT 1')
        with self.assertRaises(sqlite3.ProgrammingError): c.execute('SELECT 1')
    def test_immediate_save_and_stop(self):
        async def opened(*args): return True
        async def probe(*args):
            with m.db() as c: self.assertEqual(c.execute('SELECT count(*) FROM services').fetchone()[0],1)
            m.stop.set()
            return ('http://192.168.178.1/','Test',200,'Test','<title>Test</title>')
        with patch.object(m,'tcp_open',opened),patch.object(m,'http_probe',probe):
            asyncio.run(m.perform(['192.168.178.1'],[80,81],dict(timeout=.1,workers=1,http=True),1))
        with m.db() as c: self.assertEqual(c.execute('SELECT count(*) FROM services').fetchone()[0],1)
    def test_error_releases_lock(self):
        async def fail(*args): raise RuntimeError('injected failure')
        m.scan_lock.acquire()
        with patch.object(m,'perform',fail): m.run([],[],{},1)
        self.assertFalse(m.scan_lock.locked())
        self.assertEqual(m.state['error'],'injected failure')
    def test_finalize_failure_releases_lock(self):
        async def nothing(*args): pass
        m.scan_lock.acquire()
        with patch.object(m,'perform',nothing),patch.object(m,'db',side_effect=sqlite3.OperationalError('disk failure')):
            m.run([],[],{},1)
        self.assertFalse(m.scan_lock.locked())
    def test_scope_comparison_and_sorting(self):
        with m.db(True) as c:
            for ident,ports in [(1,'22,80'),(2,'80')]:
                c.execute("INSERT INTO scans(id,ports,state) VALUES(?,?,'done')",(ident,ports))
                c.execute('INSERT INTO scope VALUES(?,?)',(ident,'192.168.178.10'))
        m.save_open(1,'192.168.178.10',22)
        m.save_open(1,'192.168.178.10',80)
        rows=m.inventory_rows()
        self.assertEqual(rows[0]['status'],'not_checked')
        self.assertEqual(rows[1]['status'],'not_found')
        self.assertEqual(rows[1]['change'],'missing')
        m.save_open(2,'192.168.178.2',80)
        self.assertEqual(m.inventory_rows()[0]['ip'],'192.168.178.2')
    def test_auth_and_host_edit(self):
        client=m.app.test_client()
        self.assertEqual(client.get('/healthz').status_code,200)
        self.assertEqual(client.get('/api/services').status_code,401)
        client.get('/login')
        with client.session_transaction() as s: csrf=s['csrf']
        self.assertEqual(client.post('/login',data={'csrf':csrf,'password':'test-password-only-123'}).status_code,302)
        self.assertEqual(client.get('/').status_code,200)
        self.assertEqual(client.get('/static/v1.js').status_code,200)
        self.assertEqual(client.post('/api/host',json={}).status_code,403)
        m.save_open(1,'192.168.178.1',80)
        with client.session_transaction() as s: csrf=s['csrf']
        response=client.post('/api/host',json={'ip':'192.168.178.1','name':'NAS','tags':'Docker','notes':'Test'},headers={'X-CSRF-Token':csrf})
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.get('/api/services').json[0]['name'],'NAS')
if __name__=='__main__': unittest.main()
