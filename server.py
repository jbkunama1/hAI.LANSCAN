import os
import secrets
from flask import jsonify, request
import core

app = core.app
TOKEN = os.getenv('MCP_TOKEN','')
if TOKEN and (len(TOKEN)<24 or TOKEN.startswith('replace-with')):
    raise RuntimeError('MCP_TOKEN must be random, at least 24 characters, not a placeholder')
ALLOWED = {('GET','/api/status'),('GET','/api/services'),('GET','/api/scans'),('GET','/api/settings'),('POST','/api/scan'),('POST','/api/stop'),('POST','/api/host'),('POST','/api/settings')}
original = core.protect

def protect():
    if request.endpoint=='static' and request.path in ('/static/v1.css','/static/discovery.css','/static/theme.js'):
        return None
    header=request.headers.get('Authorization','')
    if header.startswith('Bearer ') and (request.method,request.path) in ALLOWED:
        supplied=header[7:].encode('utf-8')
        if TOKEN and secrets.compare_digest(supplied,TOKEN.encode('utf-8')):
            return None
        return jsonify(error='Invalid bearer token'),401
    return original()

app.before_request_funcs[None] = [protect if func is original else func for func in app.before_request_funcs.get(None,[])]

@app.get('/api/settings')
def read_settings():
    return jsonify(core.settings())

from discovery import install
install(app,core)
