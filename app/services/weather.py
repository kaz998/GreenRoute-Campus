import requests

def conditions(lat=26.8467,lon=80.9462):
    default={'temp':30,'rain':0,'wind':2,'aqi':80,'label':'Fallback conditions','source':'Default fallback'}
    try:
        w=requests.get('https://api.open-meteo.com/v1/forecast',params={'latitude':lat,'longitude':lon,'current':'temperature_2m,precipitation,wind_speed_10m','timezone':'Asia/Kolkata'},timeout=4); w.raise_for_status(); c=w.json()['current']
        a=requests.get('https://air-quality-api.open-meteo.com/v1/air-quality',params={'latitude':lat,'longitude':lon,'current':'pm2_5,european_aqi','timezone':'Asia/Kolkata'},timeout=4); a.raise_for_status(); ac=a.json()['current']
        return {'temp':c.get('temperature_2m',30),'rain':c.get('precipitation',0),'wind':c.get('wind_speed_10m',2),'aqi':ac.get('european_aqi',80),'label':'Live Open-Meteo','source':'Open-Meteo'}
    except Exception: return default
