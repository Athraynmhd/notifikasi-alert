import re
import simkuliah

c = simkuliah.SIMKULIAH()
ok = c.login('260820701100011', 'ZGBRzFgc', max_tries=10)
if not ok:
    raise SystemExit('login failed')
r = c.get('/absensi')
txt = r.text
# dump every <script> block that references ajax/DataTable/absensi
for i, m in enumerate(re.finditer(r'<script[^>]*>(.*?)</script>', txt, re.S)):
    body = m.group(1)
    low = body.lower()
    if any(k in low for k in ('datatable', 'ajax', 'absensi', 'url:')):
        print('=' * 70)
        print(f'SCRIPT #{i}')
        print(body.strip()[:4000])