import re, html as H
import simkuliah

c = simkuliah.SIMKULIAH()
ok = c.login('260820701100011', 'ZGBRzFgc', max_tries=10)
if not ok:
    raise SystemExit('login failed')
r = c.get('/absensi')
txt = r.text
links = set()
for m in re.finditer(r'href="([^"]*)"', txt):
    h = m.group(1)
    if '/index.php' in h or h.startswith('/'):
        links.add(h.split('?')[0])
print('LINKS:')
for l in sorted(links):
    print('  ', l)
# find ajax endpoints triggers
print()
print('onclick / data-url hooks:')
for m in re.finditer(r'("[^"]*(?:absencsi|absensi|jadwal|asisten)[^"]*")', txt, re.I):
    print('  ', m.group(1)[:120])