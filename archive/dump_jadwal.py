import re, html as H
import simkuliah


def textify(txt):
    txt = re.sub(r'<script.*?</script>', ' ', txt, flags=re.S)
    txt = re.sub(r'<style.*?</style>', ' ', txt, flags=re.S)
    txt = re.sub(r'</tr>', ' |ENDROW| ', txt, flags=re.I)
    txt = re.sub(r'<t[dh][^>]*>', ' [', txt, flags=re.I)
    txt = re.sub(r'</t[dh]>', '] ', txt, flags=re.I)
    txt = re.sub(r'<(br|/p|h[1-6]|/div)[^>]*>', '\n', txt, flags=re.I)
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = H.unescape(txt)
    txt = re.sub(r'[ \t]+', ' ', txt)
    txt = re.sub(r'\n{2,}', '\n', txt)
    return [ln.strip() for ln in txt.split('\n') if ln.strip()]


c = simkuliah.SIMKULIAH()
ok = c.login('260820701100011', 'ZGBRzFgc', max_tries=10)
if not ok:
    raise SystemExit('login failed')

for path in ['/jadwal_kuliah/index', '/jadwal_kuliah/jadwal_kuliah_hari_ini']:
    print('#' * 70)
    print('PATH:', path)
    r = c.get(path)
    print('  HTTP', r.status_code)
    if r.url != c.BASE + path:
        print('  redirected ->', r.url)
    lines = textify(r.text)
    for ln in lines:
        if any(k in ln for k in ('Dosen', 'dosen', 'absen', 'Absen', 'Mata Kuliah', 'Semester',
                                 'status', 'Status', 'selesai', 'Selesai', 'sudah', 'belum',
                                 'Hari', 'Jam', 'Ruangan', 'Kelas', 'SKS')):
            print('  |', ln[:200])