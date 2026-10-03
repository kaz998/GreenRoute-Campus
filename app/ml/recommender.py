import numpy as np
from sklearn.ensemble import RandomForestClassifier
from app.db import get_db

def recommend(user_id,distance,time_hour,weather):
    db=get_db(); rows=db.execute('SELECT distance_km, started_at, mode_id FROM trip_log WHERE user_id=? AND distance_km>0',(user_id,)).fetchall()
    modes=db.execute('SELECT id,code,name FROM transport_modes WHERE code IN ("walk","bicycle","erickshaw","bus","metro","motorbike","auto","car","carpool")').fetchall()
    if len(rows)<8: return {'mode':'bicycle' if distance<=6 else 'bus','name':'Bicycle' if distance<=6 else 'City Bus','confidence':72 if distance<=6 else 68,'reason':'Uses campus-wide sustainable defaults because your personal history is still small.'}
    X=[]; y=[]
    for r in rows:
        h=int(r['started_at'][11:13]) if len(r['started_at'])>13 else 8
        X.append([r['distance_km'],h]); y.append(r['mode_id'])
    model=RandomForestClassifier(n_estimators=80,random_state=42,min_samples_leaf=2); model.fit(X,y)
    p=model.predict_proba([[distance,time_hour]])[0]; idx=int(np.argmax(p)); pred=model.classes_[idx]; mode=next((m for m in modes if m['id']==pred),modes[0])
    if weather.get('rain',0)>2 and mode['code']=='bicycle': mode=next(m for m in modes if m['code']=='bus')
    return {'mode':mode['code'],'name':mode['name'],'confidence':round(float(p[idx])*100),'reason':f"Based on your past choices, trip distance and commute time; weather adjustment applied when needed."}
