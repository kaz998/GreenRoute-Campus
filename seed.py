import os, random, sqlite3
from datetime import datetime,timedelta
from werkzeug.security import generate_password_hash
from app import create_app
from app.db import get_db
random.seed(7)
app=create_app()
with app.app_context():
 db=get_db(); db.execute('DELETE FROM user_badges'); db.execute('DELETE FROM trip_log'); db.execute('DELETE FROM users'); db.execute('DELETE FROM badges'); db.execute('DELETE FROM challenges'); db.execute('DELETE FROM transport_modes')
 modes=[
 ('walk','Walk',5,0,0,0,45,1,'UK DEFRA-style active travel comparison','Approximate educational factor; walking direct emissions treated as zero.'),
 ('bicycle','Bicycle',15,0,0,0,25,1,'UK DEFRA/active travel comparison','Approximate; calories are an illustrative activity estimate.'),
 ('erickshaw','E-rickshaw',20,2.5,10,.035,0,4,'Indian urban EV comparison','Approximate electricity/emission proxy; varies by charging mix.'),
 ('bus','City Bus',22,2.5,0,.06,0,40,'CPCB/ICCT-style Indian road transport comparisons','Approximate per-passenger factor.'),
 ('metro','Metro',35,3,10,.04,0,1,'Indian Railways/ICCT-style transit comparisons','Approximate per-passenger factor; route availability varies.'),
 ('motorbike','Motorbike',38,3.2,8,.11,0,1,'ICCT/Indian two-wheeler comparisons','Approximate real-world factor.'),
 ('auto','Auto-rickshaw',25,5,10,.12,0,3,'Indian urban transport comparisons','Approximate CNG/road factor.'),
 ('car','Car',30,8.5,8,.18,0,1,'ICCT/DEFRA-style passenger car comparison','Approximate; vehicle, fuel and occupancy change results.'),
 ('carpool','Carpool',30,8.5,8,.18,0,4,'ICCT/DEFRA-style passenger car comparison','Car emissions divided across 2–4 passengers.'),]
 db.executemany('INSERT INTO transport_modes(code,name,speed_kmh,cost_per_km,fixed_cost,co2_kg_per_km,calories_per_km,shared_capacity,source,assumption) VALUES(?,?,?,?,?,?,?,?,?,?)',modes)
 badges=[('first_trip','First Trip','Logged your first green commute','🌱'),('streak_7','7-Day Streak','Logged trips across seven consecutive days','🔥'),('zero_week','Zero-Emission Week','Logged green travel across seven distinct days','🌿'),('saved_50','50 kg Saved','Saved at least 50 kg of CO₂','🌳')]
 db.executemany('INSERT INTO badges(code,name,description,icon) VALUES(?,?,?,?)',badges)
 db.executemany('INSERT INTO challenges(title,description,target,reward_points,start_date,end_date) VALUES(?,?,?,?,?,?)',[
 ('Car-free Friday','Replace a solo car trip with walking, cycling or transit.',40,100,(datetime.now()-timedelta(days=2)).date().isoformat(),(datetime.now()+timedelta(days=5)).date().isoformat()),
 ('Bike to campus week','Collect active-travel kilometres as a campus.',180,150,(datetime.now()-timedelta(days=2)).date().isoformat(),(datetime.now()+timedelta(days=5)).date().isoformat()),
 ('50 kg together','Campus-wide CO₂ saved target.',50,200,(datetime.now()-timedelta(days=2)).date().isoformat(),(datetime.now()+timedelta(days=5)).date().isoformat())])
 depts=['CSE','AI-ML','ECE','ME','CE','IT']; years=['1st','2nd','3rd','4th']; areas=['Gomti Nagar','Indira Nagar','Aliganj','Hazratganj','Alambagh','Mahanagar','Jankipuram','Chinhat']
 users=[('Demo Admin','admin@greenroute.local','admin','CSE','4th','Gomti Nagar'),('Demo Student','student@greenroute.local','student','CSE','2nd','Gomti Nagar')]
 for i in range(58): users.append((f'Demo Student {i+1}',f'student{i+1}@demo.local','student',random.choice(depts),random.choice(years),random.choice(areas)))
 for u in users: db.execute('INSERT INTO users(name,email,password_hash,role,department,year,home_area) VALUES(?,?,?,?,?,?,?)',(u[0],u[1],generate_password_hash('demo123'),u[2],u[3],u[4],u[5]))
 db.commit(); mids={r['code']:r['id'] for r in db.execute('SELECT id,code FROM transport_modes')}; users=db.execute('SELECT id,role,home_area FROM users').fetchall(); now=datetime.now()
 for u in users:
  for day in range(90):
   n=random.choices([0,1,2],[.12,.72,.16])[0]
   for _ in range(n):
    mode=random.choices(['walk','bicycle','bus','metro','erickshaw','auto','motorbike','car','carpool'],[.08,.12,.18,.12,.10,.12,.12,.13,.03])[0]
    if u['role']=='admin': continue
    hour=random.choice([7,8,8,9,17,18,18,19]); dt=(now-timedelta(days=89-day)).replace(hour=hour,minute=random.randrange(0,50),second=0,microsecond=0)
    km=max(1.5,random.gauss(7,3)); m=db.execute('SELECT * FROM transport_modes WHERE code=?',(mode,)).fetchone(); co2=km*m['co2_kg_per_km']/(m['shared_capacity'] if mode=='carpool' else 1); base=km*.18+8; saved=max(0,base-co2); cost=m['fixed_cost']+km*m['cost_per_km']; drivecost=8+km*8.5
    db.execute('INSERT INTO trip_log(user_id,mode_id,origin,destination,distance_km,duration_min,co2_kg,co2_saved_kg,money_saved,calories,weather,aqi,started_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(u['id'],mids[mode],u['home_area'],'BBDNITM',round(km,2),round(km/max(m['speed_kmh'],1)*60,1),round(co2,3),round(saved,3),round(max(0,drivecost-cost),2),round(km*m['calories_per_km'],1),'Seeded demo weather',random.choice([50,70,90,120]),dt.isoformat(' ')))
 db.commit(); print('Demo admin: admin@greenroute.local / demo123'); print('Demo student: student@greenroute.local / demo123')
