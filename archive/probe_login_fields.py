import requests, re
import captcha_utils as cu

s = cu.new_session()
r = s.get('https://simkuliah.usk.ac.id/index.php/login')
m = re.findall(r'<input[^>]*name="([^"]+)"[^>]*>', r.text)
print('inputs:', m)
m2 = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>', r.text)
print('form actions:', m2)
for line in r.text.split('\n'):
    if 'input' in line and 'name=' in line:
        t = line.strip()
        if len(t) < 220:
            print('  ', t)