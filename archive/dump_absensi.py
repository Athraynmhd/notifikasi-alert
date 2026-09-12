import re, html as H
import simkuliah

c = simkuliah.SIMKULIAH()
ok = c.login('260820701100011', 'ZGBRzFgc', max_tries=10)
if not ok:
    raise SystemExit('login failed')
r = c.get('/absensi')
txt = r.text
# remove scripts and styles
txt = re.sub(r'<script.*?</script>', ' ', txt, flags=re.S)
txt = re.sub(r'<style.*?</style>', ' ', txt, flags=re.S)
# mark table boundaries / rows
txt = re.sub(r'</tr>', ' |ENDROW| ', txt, flags=re.I)
txt = re.sub(r'<t[dh][^>]*>', ' [', txt, flags=re.I)
txt = re.sub(r'</t[dh]>', '] ', txt, flags=re.I)
txt = re.sub(r'<(br|/p|h[1-6]|/div)[^>]*>', '\n', txt, flags=re.I)
txt = re.sub(r'<[^>]+>', ' ', txt)
txt = H.unescape(txt)
txt = re.sub(r'[ \t]+', ' ', txt)
txt = re.sub(r'\n{2,}', '\n', txt)
lines = [ln.strip() for ln in txt.split('\n') if ln.strip()]
print('\n'.join(lines[:120]))