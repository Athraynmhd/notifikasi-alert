import sys, time, json, os
import numpy as np
from PIL import Image
import captcha_utils as cu
from font_solver import to_cell
from config import GLYPHS_DIR, META_JSON

n = int(sys.argv[1]) if len(sys.argv) > 1 else 20

meta = []
if os.path.exists(META_JSON):
    meta = json.loads(open(META_JSON, encoding='utf-8').read())

idx = len(meta)
cap_i = 0
while idx < n and cap_i < n * 3:
    cap_i += 1
    s = cu.new_session()
    try:
        png = cu.fetch_captcha(s)
        a = cu.read_rgb(png)
        glyphs = cu.find_char_columns(a)
        if len(glyphs) != 5:
            continue
        for pos, (x0, g) in enumerate(glyphs):
            fn = f'g_{idx}.png'
            Image.fromarray((g * 255).astype(np.uint8)).save(
                os.path.join(GLYPHS_DIR, fn))
            meta.append({'file': fn, 'pos': pos, 'x': x0})
            idx += 1
            if idx >= n:
                break
    except Exception as e:
        print(f'err: {e}')
    time.sleep(0.4)

with open(META_JSON, 'w', encoding='utf-8') as f:
    f.write(json.dumps(meta))
print(f'collected {idx} glyphs -> {GLYPHS_DIR}')