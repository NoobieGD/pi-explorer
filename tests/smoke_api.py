"""Integration tests against the running local app. Does not change digit data."""
import json, time, urllib.request, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
BASE='http://127.0.0.1:31415/api/'
def get(path): return json.load(urllib.request.urlopen(BASE+path))
status=get('status');token=status['token']
def post(path,value):
    req=urllib.request.Request(BASE+path,json.dumps(value).encode(),{'Content-Type':'application/json','X-Pi-Token':token})
    return json.load(urllib.request.urlopen(req))
def search(payload):
    job=post('search',payload)
    while True:
        result=get('job/'+job['id'])
        if result['status']!='running':break
        time.sleep(.1)
    assert result['status']=='done',result
    return result

assert status['count']>=200000
assert get('digits?start=0&count=20')['data']=='14159265358979323846'
result=search({'mode':'digits','query':'12345'})
assert result['matches'][0]['position']==49702
result=search({'mode':'text','query':'PIE','scheme':'mod26'})
assert result['matches'][0]['unitPosition']==10962
assert result['matches'][0]['position']==21923
result=search({'mode':'text','query':'CAT','scheme':'mod26'})
assert result['matches'][0]['unitPosition']==22731
rows=['11111','01010','01010','01010','01011']
result=search({'mode':'shape','rows':rows,'sweep':True,'minWidth':6,'maxWidth':320})
assert result['matches'],result
import engine
raw=Path(__file__).resolve().parents[1]/'data'/f"pi-{status['count']}.txt"
from digit_store import DigitStore
store=DigitStore(raw)
for m in result['matches']:
    for y,row in enumerate(rows):
        assert store.window(m['index']+y*m['width'],len(row),'binary')[0]==row.encode()
assert sum(get('stats')['counts'])==status['count']
assert len(get('digits?mode=text&start=0&count=100')['data'])==100
try:
    urllib.request.urlopen(urllib.request.Request(BASE+'compute',data=b'{"count":100}',headers={'Content-Type':'application/json'}))
    raise AssertionError('Mutation token should be required')
except urllib.error.HTTPError as e:assert e.code==403
print('API smoke checks passed: digits, text, verified shape sweep, stats, and request protection.')
print('Shape sweep:',len(result['matches']),'matches in',round(result['seconds'],3),'seconds')
