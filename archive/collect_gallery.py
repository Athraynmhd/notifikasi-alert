import sys, os, time
import numpy as np
import captcha_utils as cu

OUT = r'C:\Users\Lenovo\AppData\Local\Temp\opencode\glyphs'
os.makedirs(OUT, exist_ok=True)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 12

idx = 0
for i in range(n):
    s = cu.new_session()
    try:
        png = cu.fetch_captcha(s)
        a = cu.read_rgb(png)
        glyphs = cu.find_char_columns(a)
        if len(glyphs) != 5:
            print(f'sample {i}: skip, got {len(glyphs)} leaves')
            continue
        print(f'sample {i}:', end=' ')
        for x0, g in glyphs:
            fn = f'g_{i}_{idx}.png'
            fn2 = os.path.join(OUT, fn)
            from PIL import Image
            Image.fromarray((g * 255).astype(np.uint8)).save(fn2)
            print(f'[{fn}]', end=' ')
            idx += 1
        print()
    except Exception as e:
        print(f'sample {i}: EX {e}')
    time.sleep(0.6)
print(f'total glyphs saved: {idx}')