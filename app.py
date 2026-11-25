import os, secrets, hashlib, json, base64, io, hmac
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

UTC = timezone.utc
def utcnow(): return datetime.now(UTC)

app = Flask(__name__, static_folder='../frontend', static_url_path='')
database_url=os.getenv('DATABASE_URL','sqlite:///trusttrack.db')
if database_url.startswith('postgres://'):
    database_url='postgresql://'+database_url[len('postgres://'):]
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'development-only-change-me')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
origins = [x.strip() for x in os.getenv('FRONTEND_ORIGINS','http://127.0.0.1:5500,http://localhost:5500').split(',') if x.strip()] + ['http://127.0.0.1:5000','http://localhost:5000']
CORS(app, resources={r'/api/*': {'origins': origins}}, supports_credentials=True)
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__='users'; id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),nullable=False); email=db.Column(db.String(255),unique=True,nullable=False,index=True); password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(20),nullable=False); active=db.Column(db.Boolean,default=True); created_at=db.Column(db.DateTime(timezone=True),default=utcnow)
class Parcel(db.Model):
    __tablename__='parcels'; id=db.Column(db.Integer,primary_key=True); tracking_id=db.Column(db.String(24),unique=True,index=True,nullable=False); customer_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False); sender_name=db.Column(db.String(120),nullable=False); sender_phone=db.Column(db.String(40),nullable=False); receiver_name=db.Column(db.String(120),nullable=False); receiver_phone=db.Column(db.String(40),nullable=False); pickup_address=db.Column(db.Text,nullable=False); delivery_address=db.Column(db.Text,nullable=False); parcel_type=db.Column(db.String(40),nullable=False); weight_kg=db.Column(db.Float,nullable=False); description=db.Column(db.Text); delivery_mode=db.Column(db.String(30),nullable=False); status=db.Column(db.String(30),nullable=False,default='BOOKED'); qr_token=db.Column(db.String(64),unique=True,nullable=False); distance_km=db.Column(db.Float,default=0); vehicle_type=db.Column(db.String(30),default='motorcycle'); expected_delivery=db.Column(db.DateTime(timezone=True)); failed_attempts=db.Column(db.Integer,default=0); created_at=db.Column(db.DateTime(timezone=True),default=utcnow); updated_at=db.Column(db.DateTime(timezone=True),default=utcnow,onupdate=utcnow)
class CustodyEvent(db.Model):
    __tablename__='custody_events'; id=db.Column(db.Integer,primary_key=True); parcel_id=db.Column(db.Integer,db.ForeignKey('parcels.id'),nullable=False,index=True); previous_status=db.Column(db.String(30)); new_status=db.Column(db.String(30),nullable=False); previous_custodian_id=db.Column(db.Integer,db.ForeignKey('users.id')); new_custodian_id=db.Column(db.Integer,db.ForeignKey('users.id')); actor_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False); actor_role=db.Column(db.String(20),nullable=False); timestamp=db.Column(db.DateTime(timezone=True),default=utcnow); location=db.Column(db.String(255)); notes=db.Column(db.Text); qr_verification_id=db.Column(db.Integer); previous_hash=db.Column(db.String(64)); event_hash=db.Column(db.String(64),nullable=False)
class Assignment(db.Model):
    __tablename__='parcel_assignments'; id=db.Column(db.Integer,primary_key=True); parcel_id=db.Column(db.Integer,db.ForeignKey('parcels.id'),nullable=False,index=True); agent_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True); assigned_by=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False); status=db.Column(db.String(20),default='ACTIVE'); assigned_at=db.Column(db.DateTime(timezone=True),default=utcnow); released_at=db.Column(db.DateTime(timezone=True))
class OTPVerification(db.Model):
    __tablename__='otp_verifications'; id=db.Column(db.Integer,primary_key=True); parcel_id=db.Column(db.Integer,db.ForeignKey('parcels.id'),nullable=False,index=True); otp_hash=db.Column(db.String(64),nullable=False); expires_at=db.Column(db.DateTime(timezone=True),nullable=False); attempts=db.Column(db.Integer,default=0); used=db.Column(db.Boolean,default=False); created_at=db.Column(db.DateTime(timezone=True),default=utcnow)
class QRVerification(db.Model):
    __tablename__='qr_verifications'; id=db.Column(db.Integer,primary_key=True); parcel_id=db.Column(db.Integer,db.ForeignKey('parcels.id'),nullable=False); actor_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False); token_hash=db.Column(db.String(64),nullable=False); success=db.Column(db.Boolean,nullable=False); reason=db.Column(db.String(255)); created_at=db.Column(db.DateTime(timezone=True),default=utcnow)
class Notification(db.Model):
    __tablename__='notifications'; id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True); title=db.Column(db.String(120),nullable=False); message=db.Column(db.Text,nullable=False); type=db.Column(db.String(30)); read=db.Column(db.Boolean,default=False); created_at=db.Column(db.DateTime(timezone=True),default=utcnow)
class DeliveryAttempt(db.Model):
    __tablename__='delivery_attempts'; id=db.Column(db.Integer,primary_key=True); parcel_id=db.Column(db.Integer,db.ForeignKey('parcels.id'),nullable=False); actor_id=db.Column(db.Integer,db.ForeignKey('users.id')); successful=db.Column(db.Boolean,default=False); reason=db.Column(db.String(255)); attempted_at=db.Column(db.DateTime(timezone=True),default=utcnow)
class RiskAssessment(db.Model):
    __tablename__='risk_assessments'; id=db.Column(db.Integer,primary_key=True); parcel_id=db.Column(db.Integer,db.ForeignKey('parcels.id'),nullable=False,index=True); score=db.Column(db.Integer,nullable=False); category=db.Column(db.String(20),nullable=False); reasons=db.Column(db.Text); action=db.Column(db.Text); calculated_at=db.Column(db.DateTime(timezone=True),default=utcnow)
class CarbonEstimate(db.Model):
    __tablename__='carbon_estimates'; id=db.Column(db.Integer,primary_key=True); parcel_id=db.Column(db.Integer,db.ForeignKey('parcels.id'),nullable=False,index=True); distance_km=db.Column(db.Float,nullable=False); vehicle_type=db.Column(db.String(30),nullable=False); emission_factor=db.Column(db.Float,nullable=False); load_factor=db.Column(db.Float,nullable=False); co2e_kg=db.Column(db.Float,nullable=False); methodology=db.Column(db.Text); calculated_at=db.Column(db.DateTime(timezone=True),default=utcnow)
class AuditLog(db.Model):
    __tablename__='audit_logs'; id=db.Column(db.Integer,primary_key=True); actor_id=db.Column(db.Integer,db.ForeignKey('users.id')); action=db.Column(db.String(80),nullable=False); entity_type=db.Column(db.String(40)); entity_id=db.Column(db.String(40)); audit_metadata=db.Column(db.Text); created_at=db.Column(db.DateTime(timezone=True),default=utcnow)

with app.app_context():
    db.create_all()

EMISSION_FACTORS={'petrol_diesel_van':0.27,'motorcycle':0.08,'truck':0.62,'electric_vehicle':0.05}

def error(message,status=400): return jsonify(error=message),status
def require(role=None):
    uid=session.get('uid')
    if not uid: return None,error('Authentication required',401)
    u=db.session.get(User,uid)
    if not u or not u.active: return None,error('Account unavailable',401)
    if role and u.role not in ([role] if isinstance(role,str) else role): return None,error('Forbidden',403)
    return u,None

def json_error(exc):
    db.session.rollback(); return error('Invalid request',400)

@app.errorhandler(404)
def not_found(e): return jsonify(error='Not found'),404
@app.errorhandler(500)
def server_error(e): db.session.rollback(); return error('Server error',500)

@app.before_request
def csrf():
    if request.method in ('POST','PATCH','PUT','DELETE') and request.path.startswith('/api/'):
        if request.path in ('/api/login','/api/register','/api/password-reset'): return
        token=request.headers.get('X-CSRF-Token')
        if not session.get('csrf') or not token or not hmac.compare_digest(token,session['csrf']): return error('CSRF validation failed',403)

@app.route('/')
def website_home():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/health')
def health(): return jsonify(status='healthy',database='configured')

@app.post('/api/register')
def register():
    d=request.get_json(silent=True) or {}; role=d.get('role','customer')
    if role!='customer': return error('Only customer registration is public',403)
    if not d.get('name') or not d.get('email') or len(d.get('password',''))<8: return error('Valid name, email and 8-character password required')
    if User.query.filter_by(email=d['email'].lower().strip()).first(): return error('Email already registered',409)
    u=User(name=d['name'].strip(),email=d['email'].lower().strip(),password_hash=generate_password_hash(d['password']),role='customer')
    db.session.add(u); db.session.commit(); return jsonify(message='Registration successful',user={'id':u.id,'name':u.name,'role':u.role}),201

@app.post('/api/login')
def login():
    d=request.get_json(silent=True) or {}; u=User.query.filter_by(email=d.get('email','').lower().strip()).first()
    if not u or not u.active or not check_password_hash(u.password_hash,d.get('password','')): return error('Invalid credentials',401)
    if d.get('role') and d['role']!=u.role: return error('Invalid role for this account',403)
    session.clear(); session['uid']=u.id; session['csrf']=secrets.token_urlsafe(32)
    return jsonify(user={'id':u.id,'name':u.name,'email':u.email,'role':u.role},csrfToken=session['csrf'])
@app.post('/api/logout')
def logout(): session.clear(); return jsonify(message='Logged out')
@app.get('/api/me')
def me():
    u,e=require();
    if e:return e
    return jsonify(user={'id':u.id,'name':u.name,'email':u.email,'role':u.role},csrfToken=session.get('csrf'))
@app.post('/api/password-reset')
def password_reset():
    d=request.get_json(silent=True) or {}; u=User.query.filter_by(email=d.get('email','').lower().strip()).first()
    if u and d.get('password') and len(d['password'])>=8:
        u.password_hash=generate_password_hash(d['password']); db.session.commit()
    return jsonify(message='If the account exists and the input is valid, the password has been reset')

@app.route('/api/users/agents')
def agents():
    u,e=require(['dispatcher','administrator']);
    if e:return e
    result=[]
    for a in User.query.filter_by(role='agent',active=True).all():
        assigned=Assignment.query.filter_by(agent_id=a.id,status='ACTIVE').count(); delivered=Parcel.query.join(Assignment).filter(Assignment.agent_id==a.id,Assignment.status=='ACTIVE',Parcel.status=='DELIVERED').count()
        result.append({'id':a.id,'name':a.name,'email':a.email,'assigned':assigned,'delivered':delivered})
    return jsonify(agents=result)

@app.post('/api/users/agents')
def create_agent():
    u,e=require(['dispatcher','administrator']);
    if e:return e
    d=request.get_json(silent=True) or {}
    if not d.get('name') or not d.get('email') or len(d.get('password',''))<8:return error('Valid agent details required')
    if User.query.filter_by(email=d['email'].lower().strip()).first():return error('Email already registered',409)
    a=User(name=d['name'].strip(),email=d['email'].lower().strip(),password_hash=generate_password_hash(d['password']),role='agent')
    db.session.add(a);db.session.commit();AuditLog(actor_id=u.id,action='AGENT_CREATED',entity_type='user',entity_id=str(a.id));db.session.commit()
    return jsonify(message='Agent account created',agent={'id':a.id,'name':a.name,'email':a.email}),201

@app.route('/api/parcels',methods=['POST','GET'])
def parcels():
    u,e=require();
    if e:return e
    if request.method=='GET':
        status=request.args.get('status'); tracking=request.args.get('tracking')
        q=Parcel.query
        if u.role=='customer': q=q.filter_by(customer_id=u.id)
        if u.role=='agent':
            ids=[a.parcel_id for a in Assignment.query.filter_by(agent_id=u.id,status='ACTIVE').all()];q=q.filter(Parcel.id.in_(ids))
        if status:q=q.filter_by(status=status)
        if tracking:q=q.filter(Parcel.tracking_id.ilike(f'%{tracking}%'))
        return jsonify(parcels=[parcel_dict(p,u) for p in q.order_by(Parcel.created_at.desc()).all()])
    d=request.get_json(silent=True) or {}
    if u.role!='customer':return error('Only customers may book parcels',403)
    required=['sender_name','sender_phone','receiver_name','receiver_phone','pickup_address','delivery_address','parcel_type','weight_kg','delivery_mode']
    if any(not d.get(k) for k in required):return error('All required booking fields must be completed')
    weight=float(d['weight_kg']); distance=max(float(d.get('distance_km',50)),0)
    if weight<=0 or weight>10000:return error('Invalid parcel weight')
    p=Parcel(tracking_id='TT'+secrets.token_hex(6).upper(),customer_id=u.id,sender_name=d['sender_name'].strip(),sender_phone=d['sender_phone'].strip(),receiver_name=d['receiver_name'].strip(),receiver_phone=d['receiver_phone'].strip(),pickup_address=d['pickup_address'].strip(),delivery_address=d['delivery_address'].strip(),parcel_type=d['parcel_type'],weight_kg=weight,description=d.get('description',''),delivery_mode=d['delivery_mode'],qr_token=secrets.token_urlsafe(32),distance_km=distance,vehicle_type=d.get('vehicle_type','motorcycle'),expected_delivery=utcnow()+timedelta(days=3))
    db.session.add(p);db.session.flush();add_event(p,'BOOKED','NEW','Parcel booked',u,u.id,None)
    carbon=estimate_carbon(p);risk=calculate_risk(p)
    notify(p.customer_id,'Parcel booked',f"Parcel {p.tracking_id} was booked.",'parcel_booked')
    db.session.commit();return jsonify(parcel=parcel_dict(p,u),carbon=carbon,risk=risk),201

def parcel_dict(p,user=None):
    a=Assignment.query.filter_by(parcel_id=p.id,status='ACTIVE').first(); agent=db.session.get(User,a.agent_id) if a else None
    return {'id':p.id,'tracking_id':p.tracking_id,'status':p.status,'sender_name':p.sender_name,'sender_phone':p.sender_phone,'receiver_name':p.receiver_name,'receiver_phone':p.receiver_phone,'pickup_address':p.pickup_address,'delivery_address':p.delivery_address,'parcel_type':p.parcel_type,'weight_kg':p.weight_kg,'description':p.description,'delivery_mode':p.delivery_mode,'distance_km':p.distance_km,'vehicle_type':p.vehicle_type,'expected_delivery':p.expected_delivery.isoformat() if p.expected_delivery else None,'failed_attempts':p.failed_attempts,'assigned_agent':agent.name if agent else None,'created_at':p.created_at.isoformat()}

def notify(uid,title,message,kind): db.session.add(Notification(user_id=uid,title=title,message=message,type=kind))

def add_event(p,new_status,reason,notes,actor,new_custodian=None,qr_id=None):
    last=CustodyEvent.query.filter_by(parcel_id=p.id).order_by(CustodyEvent.id.desc()).first(); prev_hash=last.event_hash if last else 'GENESIS'; prev_status=p.status
    event_timestamp=utcnow()
    data=json.dumps({'parcel_id':p.id,'previous_status':prev_status,'new_status':new_status,'actor_id':actor.id,'new_custodian_id':new_custodian,'timestamp':event_timestamp.isoformat(),'location':reason,'notes':notes,'previous_hash':prev_hash},sort_keys=True)
    event_hash=hashlib.sha256(data.encode()).hexdigest(); previous_custodian_id=last.new_custodian_id if last else None
    ev=CustodyEvent(parcel_id=p.id,previous_status=prev_status,new_status=new_status,previous_custodian_id=previous_custodian_id,new_custodian_id=new_custodian,actor_id=actor.id,actor_role=actor.role,timestamp=event_timestamp,location=reason,notes=notes,qr_verification_id=qr_id,previous_hash=prev_hash,event_hash=event_hash)
    db.session.add(ev);p.status=new_status;p.updated_at=utcnow();db.session.flush();return ev

@app.get('/api/parcels/<tracking_id>')
def get_parcel(tracking_id):
    u,e=require();
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first()
    if not p:return error('Parcel not found',404)
    if u.role=='customer' and p.customer_id!=u.id:return error('Forbidden',403)
    if u.role=='agent':
        a=Assignment.query.filter_by(parcel_id=p.id,agent_id=u.id,status='ACTIVE').first()
        if not a:return error('Forbidden',403)
    risk=calculate_risk(p); carbon=latest_carbon(p)
    return jsonify(parcel=parcel_dict(p,u),risk=risk,carbon=carbon)

@app.route('/api/parcels/<tracking_id>/status',methods=['PATCH'])
def change_status(tracking_id):
    u,e=require(['dispatcher','administrator']);
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first()
    if not p:return error('Parcel not found',404)
    d=request.get_json(silent=True) or {};new=d.get('status')
    allowed={'BOOKED':['AWAITING_PICKUP','ON_HOLD','CANCELLED'],'AWAITING_PICKUP':['IN_TRANSIT','ON_HOLD','CANCELLED'],'IN_TRANSIT':['DELAYED','ON_HOLD','DELIVERED','FAILED'],'DELAYED':['IN_TRANSIT','ON_HOLD','FAILED'],'ON_HOLD':['AWAITING_PICKUP','IN_TRANSIT','CANCELLED'],'FAILED':['AWAITING_PICKUP','IN_TRANSIT','ON_HOLD','DELIVERED']}
    if new not in allowed.get(p.status,[]):return error('Invalid status transition',409)
    add_event(p,new,d.get('location',''),d.get('notes','Status updated'),u)
    notify(p.customer_id,'Parcel status updated',f"{p.tracking_id} is now {new}",'status')
    calculate_risk(p);db.session.commit();return jsonify(parcel=parcel_dict(p,u))

@app.post('/api/parcels/<tracking_id>/assign')
def assign(tracking_id):
    u,e=require(['dispatcher','administrator']);
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first();d=request.get_json(silent=True) or {}
    if not p:return error('Parcel not found',404)
    agent=db.session.get(User,int(d.get('agent_id',0)))
    if not agent or agent.role!='agent' or not agent.active:return error('Valid agent required')
    old=Assignment.query.filter_by(parcel_id=p.id,status='ACTIVE').first()
    if old:
        old.status='REASSIGNED';old.released_at=utcnow()
    Assignment(parcel_id=p.id,agent_id=agent.id,assigned_by=u.id,status='ACTIVE')
    db.session.add(Assignment(parcel_id=p.id,agent_id=agent.id,assigned_by=u.id,status='ACTIVE'))
    p.status='AWAITING_PICKUP' if p.status=='BOOKED' else p.status
    add_event(p,p.status,'ASSIGNMENT',f'Reassigned to {agent.name}' if old else f'Assigned to {agent.name}',u,agent.id)
    notify(agent.id,'Parcel assigned',f"{p.tracking_id} has been assigned to you",'assignment');notify(p.customer_id,'Parcel assigned',f"An agent has been assigned to {p.tracking_id}",'assignment')
    db.session.commit();return jsonify(message='Agent assigned',parcel=parcel_dict(p,u))

@app.get('/api/parcels/<tracking_id>/qr')
def qr(tracking_id):
    u,e=require(['customer','dispatcher','administrator','agent']);
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first()
    if not p:return error('Parcel not found',404)
    if u.role=='customer' and p.customer_id!=u.id:return error('Forbidden',403)
    try:
        import qrcode
        img=qrcode.make(p.qr_token);buf=io.BytesIO();img.save(buf,format='PNG')
        qr_image='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
    except Exception:
        qr_image=None
    return jsonify(tracking_id=p.tracking_id,verification_token=p.qr_token,qr_image=qr_image)

@app.post('/api/parcels/<tracking_id>/verify-qr')
def verify_qr(tracking_id):
    u,e=require(['agent','dispatcher','administrator']);
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first();d=request.get_json(silent=True) or {}
    if not p:return error('Parcel not found',404)
    if u.role=='agent' and not Assignment.query.filter_by(parcel_id=p.id,agent_id=u.id,status='ACTIVE').first():return error('Parcel is not assigned to this agent',403)
    success=hmac.compare_digest(p.qr_token,d.get('token',''))
    qr=QRVerification(parcel_id=p.id,actor_id=u.id,token_hash=hashlib.sha256(d.get('token','').encode()).hexdigest(),success=success,reason='Valid verification' if success else 'Invalid QR token')
    db.session.add(qr);db.session.commit()
    if not success:
        notify(p.customer_id,'Failed QR verification',f"An invalid QR verification was attempted for {p.tracking_id}",'failed_verification');return error('Invalid parcel QR token',401)
    return jsonify(message='QR verified',verified=True,parcel=parcel_dict(p,u))

@app.post('/api/parcels/<tracking_id>/handoff')
def handoff(tracking_id):
    u,e=require(['agent','dispatcher','administrator']);
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first();d=request.get_json(silent=True) or {}
    if not p:return error('Parcel not found',404)
    if u.role=='agent' and not Assignment.query.filter_by(parcel_id=p.id,agent_id=u.id,status='ACTIVE').first():return error('Parcel is not assigned to this agent',403)
    if not hmac.compare_digest(p.qr_token,d.get('token','')):return error('Invalid parcel QR token',401)
    target_status=d.get('status')
    transitions={'AWAITING_PICKUP':['PICKED_UP','IN_TRANSIT'],'PICKED_UP':['IN_TRANSIT'],'IN_TRANSIT':['DELAYED','ON_HOLD','DELIVERED','FAILED'],'DELAYED':['IN_TRANSIT','ON_HOLD','FAILED'],'ON_HOLD':['AWAITING_PICKUP','IN_TRANSIT','CANCELLED'],'FAILED':['AWAITING_PICKUP','IN_TRANSIT','ON_HOLD','DELIVERED']}
    new={'PICKED_UP':'IN_TRANSIT','IN_TRANSIT':'IN_TRANSIT','FAILED':'FAILED','DELAYED':'DELAYED'}.get(target_status)
    if not new or (target_status=='PICKED_UP' and p.status!='AWAITING_PICKUP'):
        return error('Invalid custody transition',409)
    qr=QRVerification(parcel_id=p.id,actor_id=u.id,token_hash=hashlib.sha256(d['token'].encode()).hexdigest(),success=True,reason='Custody handoff')
    db.session.add(qr);db.session.flush();assignment=Assignment.query.filter_by(parcel_id=p.id,status='ACTIVE').first()
    if target_status=='PICKED_UP': add_event(p,'IN_TRANSIT',d.get('location',''),d.get('notes','Parcel picked up'),u,u.id,qr.id); notify(p.customer_id,'Parcel picked up',f"{p.tracking_id} was picked up",'pickup')
    elif target_status=='FAILED':
        p.failed_attempts=(p.failed_attempts or 0)+1;db.session.add(DeliveryAttempt(parcel_id=p.id,actor_id=u.id,successful=False,reason=d.get('notes','Failed delivery attempt')));add_event(p,'FAILED',d.get('location',''),d.get('notes','Failed delivery attempt'),u,u.id,qr.id)
    else:add_event(p,new,d.get('location',''),d.get('notes','Custody handoff'),u,u.id,qr.id);notify(p.customer_id,'Parcel in transit',f"{p.tracking_id} is in transit",'transit')
    calculate_risk(p);db.session.commit();return jsonify(parcel=parcel_dict(p,u),message='Custody event recorded')

@app.get('/api/parcels/<tracking_id>/custody')
def custody(tracking_id):
    u,e=require();
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first()
    if not p:return error('Parcel not found',404)
    if u.role=='customer' and p.customer_id!=u.id:return error('Forbidden',403)
    events=[]
    for ev in CustodyEvent.query.filter_by(parcel_id=p.id).order_by(CustodyEvent.id).all():
        actor=db.session.get(User,ev.actor_id)
        events.append({'id':ev.id,'previous_status':ev.previous_status,'new_status':ev.new_status,'actor':actor.name if actor else None,'actor_role':ev.actor_role,'timestamp':ev.timestamp.isoformat(),'location':ev.location,'notes':ev.notes,'previous_hash':ev.previous_hash,'event_hash':ev.event_hash})
    return jsonify(events=events)

@app.get('/api/parcels/<tracking_id>/verify-chain')
def verify_chain(tracking_id):
    u,e=require();
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first()
    if not p:return error('Parcel not found',404)
    events=CustodyEvent.query.filter_by(parcel_id=p.id).order_by(CustodyEvent.id).all();previous='GENESIS';valid=True
    for ev in events:
        if ev.previous_hash!=previous:valid=False
        payload=json.dumps({'parcel_id':ev.parcel_id,'previous_status':ev.previous_status,'new_status':ev.new_status,'actor_id':ev.actor_id,'new_custodian_id':ev.new_custodian_id,'timestamp':(ev.timestamp.replace(tzinfo=UTC).isoformat() if ev.timestamp.tzinfo is None else ev.timestamp.isoformat()),'location':ev.location,'notes':ev.notes,'previous_hash':ev.previous_hash},sort_keys=True)
        if hashlib.sha256(payload.encode()).hexdigest()!=ev.event_hash:valid=False
        previous=ev.event_hash
    return jsonify(valid=valid,event_count=len(events),previous_hash=previous)

@app.post('/api/parcels/<tracking_id>/otp')
def generate_otp(tracking_id):
    u,e=require(['agent','dispatcher','administrator']);
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first()
    if not p:return error('Parcel not found',404)
    OTPVerification.query.filter_by(parcel_id=p.id,used=False).update({'used':True})
    otp=f'{secrets.randbelow(1000000):06d}'
    record=OTPVerification(parcel_id=p.id,otp_hash=hashlib.sha256(otp.encode()).hexdigest(),expires_at=utcnow()+timedelta(minutes=10));db.session.add(record)
    notify(p.customer_id,'Delivery OTP generated',f"A new delivery OTP was generated for {p.tracking_id}",'otp')
    db.session.commit()
    response={'message':'OTP generated','expires_at':record.expires_at.isoformat()}
    if os.getenv('SMS_PROVIDER','development').lower()=='development':response['development_otp']=otp
    return jsonify(response)

@app.post('/api/parcels/<tracking_id>/deliver')
def deliver(tracking_id):
    u,e=require(['agent','dispatcher','administrator']);
    if e:return e
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first();d=request.get_json(silent=True) or {}
    if not p:return error('Parcel not found',404)
    if u.role=='agent' and not Assignment.query.filter_by(parcel_id=p.id,agent_id=u.id,status='ACTIVE').first():return error('Forbidden',403)
    otp=d.get('otp','');record=OTPVerification.query.filter_by(parcel_id=p.id,used=False).order_by(OTPVerification.id.desc()).first()
    if not record:return error('No active OTP',404)
    if aware(record.expires_at)<utcnow():record.used=True;db.session.commit();return error('OTP expired',410)
    record.attempts+=1
    if record.attempts>5:record.used=True;db.session.commit();return error('OTP attempt limit exceeded',429)
    if not hmac.compare_digest(record.otp_hash,hashlib.sha256(str(otp).encode()).hexdigest()):db.session.commit();return error('Invalid OTP',401)
    record.used=True;db.session.add(DeliveryAttempt(parcel_id=p.id,actor_id=u.id,successful=True));add_event(p,'DELIVERED',d.get('location',''),d.get('notes','Receiver verification successful'),u,u.id)
    old=Assignment.query.filter_by(parcel_id=p.id,status='ACTIVE').first()
    if old:old.status='COMPLETED';old.released_at=utcnow()
    notify(p.customer_id,'Parcel delivered',f"{p.tracking_id} was delivered",'delivered')
    calculate_risk(p);db.session.commit();return jsonify(message='Parcel delivered',parcel=parcel_dict(p,u))

@app.post('/api/parcels/<tracking_id>/public-otp')
def public_placeholder(tracking_id): return error('Receiver OTP verification uses /api/parcels/<tracking_id>/deliver',404)

@app.get('/api/public/track/<tracking_id>')
def public_track(tracking_id):
    p=Parcel.query.filter_by(tracking_id=tracking_id.upper()).first()
    if not p:return error('Parcel not found',404)
    events=CustodyEvent.query.filter_by(parcel_id=p.id).order_by(CustodyEvent.id).all()
    return jsonify(tracking_id=p.tracking_id,status=p.status,pickup=p.pickup_address,delivery=p.delivery_address,expected_delivery=p.expected_delivery.isoformat() if p.expected_delivery else None,timeline=[{'status':e.new_status,'timestamp':e.timestamp.isoformat()} for e in events])

def aware(dt):
    return dt.replace(tzinfo=UTC) if dt and dt.tzinfo is None else dt

def calculate_risk(p):
    score=0;reasons=[]
    elapsed=max((utcnow()-aware(p.created_at)).total_seconds()/86400,0)
    if p.status=='DELAYED':score+=35;reasons.append('Parcel is delayed')
    if p.status=='FAILED':score+=30;reasons.append('Delivery failure recorded')
    if p.status in ('IN_TRANSIT','AWAITING_PICKUP') and elapsed>3:score+=25;reasons.append('Milestone time exceeded')
    last=CustodyEvent.query.filter_by(parcel_id=p.id).order_by(CustodyEvent.id.desc()).first()
    if last:
        idle=(utcnow()-aware(last.timestamp)).total_seconds()/86400
        if idle>2:score+=15;reasons.append('No recent custody update')
    if p.expected_delivery and utcnow()>aware(p.expected_delivery):score+=20;reasons.append('Expected delivery time passed')
    score=min(100,score+(p.failed_attempts or 0)*10)
    if p.failed_attempts:reasons.append(f'{p.failed_attempts} failed delivery attempt(s)')
    category='LOW' if score<=30 else 'MEDIUM' if score<=60 else 'HIGH'
    action='Continue monitoring' if category=='LOW' else 'Review delivery milestone' if category=='MEDIUM' else 'Dispatch follow-up immediately'
    db.session.add(RiskAssessment(parcel_id=p.id,score=score,category=category,reasons='; '.join(reasons) or 'No elevated risk factors',action=action));db.session.commit();return {'score':score,'category':category,'reasons':reasons or ['No elevated risk factors'],'action':action}

def estimate_carbon(p):
    factor=EMISSION_FACTORS.get(p.vehicle_type,EMISSION_FACTORS['motorcycle']);load_factor=min(1.0,max(0.05,p.weight_kg/100));co2=p.distance_km*factor*load_factor
    r=CarbonEstimate(parcel_id=p.id,distance_km=p.distance_km,vehicle_type=p.vehicle_type,emission_factor=factor,load_factor=load_factor,co2e_kg=co2,methodology='Distance × vehicle emission factor × load allocation factor')
    db.session.add(r);db.session.commit();return {'distance_km':p.distance_km,'vehicle_type':p.vehicle_type,'emission_factor':factor,'load_factor':round(load_factor,4),'co2e_kg':round(co2,3),'estimated':True,'methodology':'Distance × vehicle emission factor × load allocation factor'}
def latest_carbon(p):
    r=CarbonEstimate.query.filter_by(parcel_id=p.id).order_by(CarbonEstimate.id.desc()).first()
    return {'distance_km':r.distance_km,'vehicle_type':r.vehicle_type,'emission_factor':r.emission_factor,'load_factor':r.load_factor,'co2e_kg':round(r.co2e_kg,3),'estimated':True,'methodology':r.methodology} if r else None

@app.get('/api/notifications')
def notifications():
    u,e=require();
    if e:return e
    n=Notification.query.filter_by(user_id=u.id).order_by(Notification.created_at.desc()).limit(50).all()
    return jsonify(notifications=[{'id':x.id,'title':x.title,'message':x.message,'type':x.type,'read':x.read,'created_at':x.created_at.isoformat()} for x in n])
@app.patch('/api/notifications/<int:nid>/read')
def read_notification(nid):
    u,e=require();
    if e:return e
    n=db.session.get(Notification,nid)
    if not n or n.user_id!=u.id:return error('Notification not found',404)
    n.read=True;db.session.commit();return jsonify(message='Read')

@app.get('/api/analytics')
def analytics():
    u,e=require(['dispatcher','administrator']);
    if e:return e
    parcels=Parcel.query.all();delivered=[p for p in parcels if p.status=='DELIVERED'];carbon=sum((latest_carbon(p) or {}).get('co2e_kg',0) for p in parcels)
    total=len(parcels);times=[]
    for p in delivered:
        ev=CustodyEvent.query.filter_by(parcel_id=p.id,new_status='DELIVERED').first()
        if ev:times.append((ev.timestamp-p.created_at).total_seconds()/3600)
    return jsonify({'total':total,'booked':sum(p.status=='BOOKED' for p in parcels),'awaiting_pickup':sum(p.status=='AWAITING_PICKUP' for p in parcels),'in_transit':sum(p.status=='IN_TRANSIT' for p in parcels),'delivered':len(delivered),'delayed':sum(p.status=='DELAYED' for p in parcels),'high_risk':sum((RiskAssessment.query.filter_by(parcel_id=p.id).order_by(RiskAssessment.id.desc()).first() or RiskAssessment(score=0,category='LOW')).category=='HIGH' for p in parcels),'active_agents':User.query.filter_by(role='agent',active=True).count(),'completion_rate':round(len(delivered)/total*100,1) if total else 0,'average_delivery_hours':round(sum(times)/len(times),1) if times else 0,'carbon_kg':round(carbon,3)})
@app.get('/api/analytics/agents')
def agent_analytics():
    u,e=require(['dispatcher','administrator']);
    if e:return e
    rows=[]
    for agent in User.query.filter_by(role='agent',active=True).all():
        a_ids=[x.parcel_id for x in Assignment.query.filter_by(agent_id=agent.id).all()]; parcels=Parcel.query.filter(Parcel.id.in_(a_ids)).all()
        delivered=sum(p.status=='DELIVERED' for p in parcels);failed=sum(p.failed_attempts or 0 for p in parcels)
        rows.append({'id':agent.id,'name':agent.name,'completed':delivered,'assigned':len(parcels),'successful_percentage':round(delivered/(delivered+failed)*100,1) if delivered+failed else 0})
    return jsonify(agents=rows)
@app.get('/api/analytics/carbon')
def carbon_analytics():
    u,e=require(['dispatcher','administrator','customer']);
    if e:return e
    q=CarbonEstimate.query
    if u.role=='customer':
        ids=[p.id for p in Parcel.query.filter_by(customer_id=u.id).all()];q=q.filter(CarbonEstimate.parcel_id.in_(ids))
    estimates=q.all();return jsonify(total_co2e_kg=round(sum(r.co2e_kg for r in estimates),3),parcel_count=len(set(r.parcel_id for r in estimates)),methodology='Estimated from configurable vehicle emission factors and parcel load allocation; not certified measurement')
@app.get('/api/analytics/risk')
def risk_analytics():
    u,e=require(['dispatcher','administrator']);
    if e:return e
    rows=[]
    for p in Parcel.query.all():
        r=RiskAssessment.query.filter_by(parcel_id=p.id).order_by(RiskAssessment.id.desc()).first()
        if r:rows.append({'tracking_id':p.tracking_id,'status':p.status,'score':r.score,'category':r.category,'reasons':r.reasons,'action':r.action})
    return jsonify(risk=[x for x in rows if x['category']=='HIGH'],all=rows)

@app.route('/api/<path:path>',methods=['GET','POST','PATCH','DELETE','PUT'])
def unknown_api(path):return error('Endpoint not found',404)

@app.get('/<path:path>')
def frontend(path):
    file=os.path.join(app.static_folder,path)
    return send_from_directory(app.static_folder,path) if os.path.isfile(file) else send_from_directory(app.static_folder,'index.html')

if __name__=='__main__':
    with app.app_context():db.create_all()
    app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')))
