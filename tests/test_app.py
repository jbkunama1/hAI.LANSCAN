import importlib, os, tempfile, unittest
os.environ['SECRET_KEY']='test-key-only-not-for-production'
os.environ['ADMIN_PASSWORD']='test-password-only'
os.environ['DB_PATH']=os.path.join(tempfile.mkdtemp(),'index.sqlite')
os.environ['ALLOWED_NETWORKS']='192.168.178.0/24'
module=importlib.import_module('app')
class Tests(unittest.TestCase):
    def test_ports(self):
        self.assertEqual(module.parse_ports('22,80-82'),[22,80,81,82])
        with self.assertRaises(ValueError): module.parse_ports('0')
    def test_targets(self):
        self.assertEqual(len(module.parse_targets('192.168.178.10-12')),3)
        with self.assertRaises(ValueError): module.parse_targets('8.8.8.8')
        with self.assertRaises(ValueError): module.parse_targets('192.168.0.0/16')
    def test_auth(self):
        client=module.app.test_client()
        self.assertEqual(client.get('/api/services').status_code,401)
        client.get('/login')
        with client.session_transaction() as s: token=s['csrf']
        self.assertEqual(client.post('/login',data={'csrf':token,'password':'test-password-only'}).status_code,302)
        self.assertEqual(client.get('/').status_code,200)
        self.assertEqual(client.get('/api/services').status_code,200)
        self.assertEqual(client.post('/api/settings',json={}).status_code,403)
        with client.session_transaction() as s: token=s['csrf']
        config=module.settings(); config['theme']='light'
        self.assertEqual(client.post('/api/settings',json=config,headers={'X-CSRF-Token':token}).status_code,200)
    def test_templates(self):
        for name in ('index.html','login.html'): module.app.jinja_env.get_template(name)
if __name__=='__main__': unittest.main()
