import sys, json
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
paths = sys.argv[2:]; base = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1440, 390):
        for path in paths:
            for name, root in (('live', 'https://www.faithbaptistnpr.com'), ('new', base)):
                pg = b.new_page(viewport={'width': w, 'height': 900})
                url = root + (path if not (name == 'live' and path == '/') else '/home')
                pg.goto(url, wait_until='load', timeout=90000)
                pg.wait_for_timeout(1500)
                pg.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,120))}}"); pg.wait_for_timeout(800); pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(500)
                f = f'/tmp/cmp/{name}-{w}-{path.strip("/").replace("/","_") or "home"}.png'
                pg.screenshot(path=f, full_page=True); pg.close()
            a = Image.open(f.replace('/new-', '/live-')).convert('RGB'); n = Image.open(f).convert('RGB')
            h = min(a.height, n.height)
            d = ImageChops.difference(a.crop((0, 0, w, h)), n.crop((0, 0, w, h)))
            bbox = d.getbbox()
            px = sum(1 for v in d.convert('L').point(lambda x: 255 if x > 40 else 0).getdata() if v) / (w * h)
            print(f'{w} {path:40s} live_h={a.height} new_h={n.height} diff={px:.3%} bbox={bbox}', flush=True)
