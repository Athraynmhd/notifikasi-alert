import re, json
import simkuliah

c = simkuliah.SIMKULIAH()
ok = c.login('260820701100011', 'ZGBRzFgc', max_tries=10)
if not ok:
    raise SystemExit('login failed')

for path in ['/absensi', '/absensi/absen_asisten_lab']:
    print('#' * 70)
    print('PATH:', path)
    r = c.get(path)
    print('  HTTP', r.status_code, '| final:', r.url)
    txt = r.text
    # find absen-related raw lines
    for line in txt.split('\n'):
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if ('absen' in low or 'dosen' in low or 'belum' in low or 'sudah' in low
                or 'menunggu' in low or 'bid' in low or 'data-' in low):
            print('   |', s[:240])