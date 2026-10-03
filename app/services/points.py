from datetime import datetime, timedelta
from app.db import get_db

def stats(user_id):
    db=get_db(); r=db.execute('SELECT COALESCE(SUM(co2_saved_kg),0) saved, COALESCE(SUM(money_saved),0) money, COALESCE(SUM(calories),0) calories, COUNT(*) trips FROM trip_log WHERE user_id=?',(user_id,)).fetchone()
    return dict(r)

def level(points):
    return 'Seedling' if points<50 else 'Sapling' if points<150 else 'Tree' if points<300 else 'Forest'

def award_badges(user_id):
    db=get_db(); s=stats(user_id); badges=[]
    if s['trips']>=1: badges.append('first_trip')
    if s['saved']>=50: badges.append('saved_50')
    rows=db.execute('SELECT DISTINCT substr(started_at,1,10) d FROM trip_log WHERE user_id=? ORDER BY d',(user_id,)).fetchall()
    days={r['d'] for r in rows}; streak=0; cur=datetime.now().date()
    while cur.isoformat() in days: streak+=1; cur-=timedelta(days=1)
    if streak>=7: badges.append('streak_7')
    if len(days)>=7: badges.append('zero_week')
    for code in badges:
        b=db.execute('SELECT id FROM badges WHERE code=?',(code,)).fetchone()
        if b: db.execute('INSERT OR IGNORE INTO user_badges(user_id,badge_id) VALUES(?,?)',(user_id,b['id']))
    db.commit(); return streak
