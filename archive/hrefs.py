import re
import simkuliah

c = simkuliah.SIMKULIAH()
ok = c.login('260820701100011', 'ZGBRzFgc', max_tries=10)
if not ok:
    raise SystemExit('login failed')
r = c.get('/absensi')
txt = r.text
for m in sorted(set(re.findall(r'href=["\']([^"\']+)["\']', txt))):
    if '/index.php' in m and 'assets' not in m:
        print(m)
print('---forms---')
for m in re.findall(r'<form[^>]*action=["\']([^"\']+)["\'][^>]*>', txt):
    print(m)