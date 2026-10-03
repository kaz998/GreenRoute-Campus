import os,tempfile
import pytest
from app import create_app
from app.services.routing import haversine
@pytest.fixture
def app():
 p=tempfile.NamedTemporaryFile(delete=False).name; a=create_app({'TESTING':True,'DATABASE':p,'WTF_CSRF_ENABLED':False,'RATELIMIT_ENABLED':False}); yield a; os.unlink(p)
def test_haversine(app): assert haversine(26.8467,80.9462,26.8467,80.9462)==0
def test_auth_and_route_api(app):
 c=app.test_client(); r=c.post('/register',data={'name':'A','email':'a@example.com','password':'secret123','department':'CSE','year':'1st','home_area':'Gomti Nagar'},follow_redirects=True); assert r.status_code==200
 c.post('/login',data={'email':'a@example.com','password':'secret123'}); r=c.post('/api/route',json={'olat':26.8467,'olon':80.9462,'dlat':26.85,'dlon':80.95}); assert r.status_code==200 and r.json['distance_km']>0
def test_compare(app):
 c=app.test_client(); c.post('/register',data={'name':'A','email':'a2@example.com','password':'secret123'}); c.post('/login',data={'email':'a2@example.com','password':'secret123'}); r=c.post('/api/compare',json={'distance_km':5}); assert r.status_code==200 and len(r.json['items'])>=8
