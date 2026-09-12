import re
import simkuliah

c = simkuliah.SIMKULIAH()
ok = c.login('260820701100011', 'ZGBRzFgc', max_tries=10)
if not ok:
    raise SystemExit('login failed')
r = c.get('/jadwal_kuliah/jadwal_kuliah_asisten_lab')
txt = r.text
# print raw <table>...</table> with minimal trimming
m = re.search(r'<table[\s\S]*?</table>', txt, re.I)
if m:
    t = m.group(0)
    t = re.sub(r'\s+', ' ', t)
    print(t[:6000])
else:
    print('no table found')