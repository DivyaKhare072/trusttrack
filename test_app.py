import os, pytest
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['SECRET_KEY']='test-secret'
from app import app, db, User

@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all(); db.create_all()
        from werkzeug.security import generate_password_hash
        db.session.add(User(name='Dispatcher',email='dispatcher@test.local',password_hash=generate_password_hash('Password123'),role='dispatcher'))
        db.session.commit()
    with app.test_client() as c:
        yield c

def login(c,email,password,role):
    r=c.post('/api/login',json={'email':email,'password':password,'role':role}); assert r.status_code==200
    return r.get_json()['csrfToken']
def stateful_post(c,path,data,csrf):
    return c.post(path,json=data,headers={'X-CSRF-Token':csrf})

def test_register_and_role_permissions(client):
    r=client.post('/api/register',json={'name':'Customer','email':'customer@test.local','password':'Password123','role':'customer'}); assert r.status_code==201
    r=client.post('/api/register',json={'name':'Bad','email':'agent@test.local','password':'Password123','role':'agent'}); assert r.status_code==403

def test_login_unauthorized_customer_access(client):
    r=client.post('/api/login',json={'email':'missing@test.local','password':'bad','role':'customer'}); assert r.status_code==401

def test_book_assign_qr_otp_delivery_chain(client):
    r=client.post('/api/register',json={'name':'Customer','email':'customer@test.local','password':'Password123','role':'customer'}); assert r.status_code==201
    csrf=login(client,'customer@test.local','Password123','customer')
    r=stateful_post(client,'/api/parcels',{'sender_name':'Sam','sender_phone':'1','receiver_name':'Rae','receiver_phone':'2','pickup_address':'A','delivery_address':'B','parcel_type':'Package','weight_kg':2,'delivery_mode':'Standard','distance_km':20,'vehicle_type':'motorcycle'},csrf); assert r.status_code==201
    tracking=r.get_json()['parcel']['tracking_id']
    client.post('/api/logout',json={},headers={'X-CSRF-Token':csrf})
    dispatcher_csrf=login(client,'dispatcher@test.local','Password123','dispatcher')
    r=stateful_post(client,'/api/users/agents',{'name':'Agent','email':'agent@test.local','password':'Password123'},dispatcher_csrf); assert r.status_code==201
    agent_id=r.get_json()['agent']['id']
    r=stateful_post(client,f'/api/parcels/{tracking}/assign',{'agent_id':agent_id},dispatcher_csrf); assert r.status_code==200
    client.post('/api/logout',json={},headers={'X-CSRF-Token':dispatcher_csrf})
    agent_csrf=login(client,'agent@test.local','Password123','agent')
    detail=client.get(f'/api/parcels/{tracking}/qr',headers={'X-CSRF-Token':agent_csrf}).get_json(); token=detail['verification_token']
    r=stateful_post(client,f'/api/parcels/{tracking}/handoff',{'token':token,'status':'PICKED_UP','location':'Depot'},agent_csrf); assert r.status_code==200
    r=stateful_post(client,f'/api/parcels/{tracking}/otp',{},agent_csrf); assert r.status_code==200
    otp=r.get_json()['development_otp']
    r=stateful_post(client,f'/api/parcels/{tracking}/deliver',{'otp':'000000','location':'Door'},agent_csrf); assert r.status_code in (401,400)
    r=stateful_post(client,f'/api/parcels/{tracking}/deliver',{'otp':otp,'location':'Door'},agent_csrf); assert r.status_code==200
    r=stateful_post(client,f'/api/parcels/{tracking}/deliver',{'otp':otp,'location':'Door'},agent_csrf); assert r.status_code in (404,401,403)
    chain=client.get(f'/api/parcels/{tracking}/verify-chain'); assert chain.status_code==200 and chain.get_json()['valid'] is True
