"""One-time mirror of the Squarespace site into static source files.
Run from repo root: python3 tools/mirror.py"""
import re, os, json, hashlib, urllib.request, urllib.parse, concurrent.futures as cf
from bs4 import BeautifulSoup, Comment

BASE = 'https://www.faithbaptistnpr.com'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36'}
SRC = 'src'; PUB_ASSETS = os.path.join(SRC, 'static', 'assets')
os.makedirs(PUB_ASSETS, exist_ok=True)
cache = {}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get('Content-Type', '')

def norm(u):
    u = u.strip()
    if u.startswith('//'): u = 'https:' + u
    return u

ASSET_HOSTS = ('images.squarespace-cdn.com', 'static1.squarespace.com', 'assets.squarespace.com',
               'definitions.sqspcdn.com', 'study.faithbaptistnpr.com')

def local_name(u):
    p = urllib.parse.urlparse(u)
    base = os.path.basename(p.path) or 'file'
    base = re.sub(r'[^A-Za-z0-9._-]', '_', urllib.parse.unquote(base))[-80:]
    h = hashlib.sha1(p.netloc.encode() + p.path.encode()).hexdigest()[:10]
    if p.netloc == 'images.squarespace-cdn.com': sub = 'img'
    elif base.endswith('.css') : sub = 'css'
    else: sub = 'misc'
    return f'{sub}/{h}-{base}'

def fetch_asset(u):
    """Download asset, return local URL path. CSS is rewritten recursively."""
    u = norm(u)
    p = urllib.parse.urlparse(u)
    if p.netloc not in ASSET_HOSTS: return None
    key = p.netloc + p.path + ('?' + p.query if p.netloc != 'images.squarespace-cdn.com' and p.path.endswith('.css') else '')
    if key in cache: return cache[key]
    name = local_name(u)
    if p.netloc == 'images.squarespace-cdn.com':
        dl = urllib.parse.urlunparse(p._replace(query='format=2500w', fragment=''))
    else:
        dl = urllib.parse.urlunparse(p._replace(fragment=''))
    path = os.path.join(PUB_ASSETS, name)
    cache[key] = '/assets/' + name
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            data, ct = get(dl)
        except Exception as e:
            if p.netloc == 'images.squarespace-cdn.com':
                data, ct = get(urllib.parse.urlunparse(p._replace(query='', fragment='')))
            else:
                print('FAIL', dl, e); cache[key] = None; return None
        if name.endswith('.css') or 'text/css' in ct:
            data = rewrite_css(data.decode('utf-8', 'replace'), dl).encode()
        open(path, 'wb').write(data)
    return cache[key]

def rewrite_css(css, base):
    # drop squarespace UI/social icon fonts? keep (they are used for icons)
    def rep(m):
        raw = m.group(2).strip()
        if raw.startswith('data:') or raw.startswith('#'): return m.group(0)
        full = urllib.parse.urljoin(base, norm(raw))
        frag = '#' + full.split('#', 1)[1] if '#' in full else ''
        loc = fetch_asset(full.split('#')[0])
        return f"url('{loc}{frag}')" if loc else m.group(0)
    return re.sub(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)", rep, css)

KEEP_INLINE_MARKERS = ('fbc-pill', 'fbx-foot', 'reserveSpaceForHeader')

def is_sqs_script(t):
    src = t.get('src', '')
    if src: return 'tithe.ly' not in src
    typ = t.get('type', '')
    if typ == 'application/ld+json': return False
    txt = t.string or t.text or ''
    if any(k in txt for k in KEEP_INLINE_MARKERS): return False
    return True

def form_html(cfg, form_id_hint):
    """Render a static form matching Squarespace form markup classes."""
    fields = cfg.get('formFields', [])
    out = [f'<form class="fbc-form react-form-contents" method="post" action="/api/form" data-form-name="{cfg.get("formName","Form")}">',
           f'<input type="hidden" name="_form" value="{cfg.get("formName","Form")}">',
           '<div class="hp" aria-hidden="true" style="position:absolute;left:-10000px"><label>Leave blank<input type="text" name="_hp" tabindex="-1" autocomplete="off"></label></div>',
           '<div class="field-list">']
    for f in fields:
        typ = f.get('type'); title = f.get('title') or f.get('label') or typ
        req = ' required' if f.get('required') else ''
        reqmark = ' <span class="required" aria-hidden="true">*</span>' if f.get('required') else ''
        nm = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
        desc = f.get('description') or ''
        out.append(f'<div class="form-item field {typ}">')
        if typ == 'name':
            out.append(f'<fieldset><legend class="title">{title}{reqmark}</legend><div class="field-row">'
                       f'<label class="field first-name"><span class="caption">First Name</span><input class="field-element" type="text" name="first_name" autocomplete="given-name"{req}></label>'
                       f'<label class="field last-name"><span class="caption">Last Name</span><input class="field-element" type="text" name="last_name" autocomplete="family-name"{req}></label></div></fieldset>')
        elif typ == 'radio' or typ == 'checkbox':
            opts = f.get('options') or []
            out.append(f'<fieldset><legend class="title">{title}{reqmark}</legend>')
            for i, o in enumerate(opts):
                ov = o if isinstance(o, str) else (o.get('name') or o.get('label') or o.get('value'))
                r = req if (typ == 'radio' and i == 0) else ''
                out.append(f'<div class="option"><label><input type="{typ}" name="{nm}" value="{ov}"{r}> {ov}</label></div>')
            out.append('</fieldset>')
        else:
            label = f'<label class="title" for="f-{nm}">{title}{reqmark}</label>'
            if desc: label += f'<p class="description">{desc}</p>'
            if typ == 'textarea':
                ctl = f'<textarea class="field-element" id="f-{nm}" name="{nm}"{req}></textarea>'
            else:
                it = {'email': 'email', 'phone': 'tel', 'date': 'date', 'number': 'number'}.get(typ, 'text')
                ctl = f'<input class="field-element" id="f-{nm}" type="{it}" name="{nm}"{req}>'
            out.append(label + ctl)
        out.append('</div>')
    btn = cfg.get('formSubmitButtonText') or 'Submit'
    out.append('</div>')
    out.append(f'<div class="form-button-wrapper form-button-wrapper--align-left"><button class="button sqs-system-button sqs-editable-button sqs-button-element--primary" type="submit">{btn}</button></div>')
    msg = cfg.get('formSubmissionMessage') or {}
    msgtxt = BeautifulSoup(msg.get('html', '') if isinstance(msg, dict) else str(msg), 'lxml').get_text(' ', strip=True) or 'Thank you!'
    out.append(f'<div class="form-submission-text" hidden>{msgtxt}</div><div class="form-error-text" hidden>Sorry, something went wrong. Please try again.</div></form>')
    return ''.join(out)

def process(url):
    html, _ = get(url)
    s = BeautifulSoup(html, 'lxml')
    for c in s.find_all(string=lambda x: isinstance(x, Comment)): c.extract()
    # forms: replace each form block's JSON config with static form
    for blk in s.select('.sqs-block.form-block, .sqs-block-form'):
        cfgtag = None
        for t in blk.find_all('script', type='application/json'):
            try:
                d = json.loads(t.string or t.text)
                if 'formFields' in d: cfgtag = d
            except Exception: pass
        if cfgtag:
            content = blk.select_one('.sqs-block-content') or blk
            content.clear()
            content.append(BeautifulSoup(form_html(cfgtag, blk.get('id')), 'lxml').form)
    for t in s.find_all('script'):
        if is_sqs_script(t): t.decompose()
    for t in s.find_all('link'):
        rel = ' '.join(t.get('rel', []))
        href = t.get('href', '')
        if 'stylesheet' in rel or 'icon' in rel:
            loc = fetch_asset(urllib.parse.urljoin(url, href))
            if loc: t['href'] = loc
            elif 'typekit' in href: t.decompose()
        elif rel in ('preconnect', 'dns-prefetch', 'preload', 'modulepreload') or 'squarespace' in href:
            t.decompose()
    for t in s.find_all('meta'):
        if t.get('content', '').startswith(('//images.squarespace-cdn.com', 'http://static1', 'https://images.squarespace-cdn.com', 'http://images.squarespace-cdn.com')):
            loc = fetch_asset(t['content'].replace('http://', 'https://'))
            if loc: t['content'] = BASE.replace('www.', '') + loc
    # images
    for t in s.find_all(True):
        for attr in ('src', 'data-src', 'data-image', 'href', 'poster'):
            v = t.get(attr)
            if v and ('squarespace-cdn.com' in v or 'static1.squarespace.com' in v):
                if t.name == 'a' and attr == 'href' and not re.search(r'\.(jpe?g|png|gif|webp|svg|pdf)', v, re.I): continue
                loc = fetch_asset(v)
                if loc: t[attr] = loc
        if t.has_attr('srcset') and 'squarespace' in t['srcset']:
            parts = []
            for part in t['srcset'].split(','):
                bits = part.strip().split()
                if not bits: continue
                loc = fetch_asset(bits[0])
                if loc and loc not in [p.split()[0] for p in parts]: parts.append(loc + (' ' + bits[1] if len(bits) > 1 else ''))
            if parts: t['srcset'] = ', '.join(parts)
            else: del t['srcset']
        if t.has_attr('style') and 'url(' in t['style']:
            t['style'] = rewrite_css(t['style'], url)
    for img in s.find_all('img'):
        if img.get('data-src') and not img.get('src'):
            img['src'] = img['data-src']
        if img.get('data-src') and img.get('src') != img['data-src'] and 'squarespace' in img.get('src', ''):
            img['src'] = img['data-src']
        if img.get('src', '').startswith('/assets/img') and 'srcset' in img.attrs and 'squarespace' in img['srcset']:
            del img['srcset']
    for st in s.find_all('style'):
        if st.string and 'url(' in st.string: st.string = rewrite_css(st.string, url)
    # internal links
    for a in s.find_all('a', href=True):
        h = a['href']
        for pre in ('https://www.faithbaptistnpr.com', 'https://faithbaptistnpr.com', 'http://www.faithbaptistnpr.com'):
            if h.startswith(pre): h = h[len(pre):] or '/'
        if h == '/home' or h.startswith('/home?'): h = '/'
        a['href'] = h
    return str(s)

if __name__ == '__main__':
    sm = get(BASE + '/sitemap.xml')[0].decode()
    urls = [u for u in re.findall(r'<loc>([^<]+)</loc>', sm) if 'squarespace-cdn' not in u]
    os.makedirs(os.path.join(SRC, 'pages'), exist_ok=True)
    def one(u):
        path = urllib.parse.urlparse(u).path.strip('/') or 'home'
        out = os.path.join(SRC, 'pages', path + '.html')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'w').write(process(u))
        return path
    for u in urls:
        print(one(u))
    json.dump(sorted(urls), open(os.path.join(SRC, 'sitemap-urls.json'), 'w'), indent=1)
