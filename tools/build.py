import re
"""Build the static site into public/.
  python3 tools/build.py && npx -y pagefind --site public
Pages come from src/pages, events from data/events.json, static files from src/static."""
import json, os, re, shutil, glob, html, urllib.parse, datetime as dt
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = 'https://faithbaptistnpr.com'
TZ = ZoneInfo('America/New_York')
OUT = 'public'
shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree('src/static', OUT)
NOW = dt.datetime.now(dt.timezone.utc)
E_ = html.escape

def soup(path): return BeautifulSoup(open(path, encoding='utf-8'), 'lxml')

ANNOUNCE = """<div class="sqs-announcement-bar-custom-location"><div class="yui3-widget sqs-widget sqs-announcement-bar"><div class="sqs-announcement-bar-content"><a class="sqs-announcement-bar-url" href="/plan-your-visit" aria-labelledby="announcement-bar-text-inner-id"></a><div class="sqs-announcement-bar-text"><span class="sqs-announcement-bar-close" tabindex="0" role="button" aria-label="Close Announcement"></span><div id="announcement-bar-text-inner-id" class="sqs-announcement-bar-text-inner"><p data-rte-preserve-empty="true" style="white-space:pre-wrap;">Services: Sundays on Campus &amp; Online @ 9:00am &amp; 10:45am</p></div></div></div></div></div>"""

def finalize(s, path):
    """Common post-processing for every page."""
    head = s.head
    for m in s.select('meta[name=robots]'): m.decompose()
    head.insert(0, BeautifulSoup('<meta name="robots" content="noindex, nofollow">', 'lxml').meta)
    # self-hosted fonts + site script
    head.append(BeautifulSoup('<link rel="stylesheet" href="/assets/fonts/fonts.css">', 'lxml').link)
    head.append(BeautifulSoup('<link rel="stylesheet" href="/assets/site.css">', 'lxml').link)
    s.body.append(BeautifulSoup('<script src="/assets/site.js" defer></script>', 'lxml').script)
    dz = s.select_one('.sqs-announcement-bar-dropzone')
    if dz is not None and not dz.contents:
        dz.append(BeautifulSoup(ANNOUNCE, 'html.parser'))
    for root in s.select('.fluid-image-component-root'):
        fit = 'cover' if root.get('data-is-image-stretched') == 'true' else 'contain'
        fp = (root.get('data-media-focal-point') or '0.5,0.5').split(',')
        try: pos = f"{float(fp[0])*100:.1f}% {float(fp[1])*100:.1f}%"
        except Exception: pos = '50% 50%'
        root['style'] = f"--image-component-object-fit: {fit}; --image-component-focal-point: {pos}; --image-component-container-height: 100%; --image-component-container-width: 100%;"
    for g in s.select('.gallery-grid'):
        w = g.select_one('.gallery-grid-wrapper')
        if w is None: continue
        cols = g.get('data-columns') or '3'; gut = float(g.get('data-gutter') or 0) / 20
        w['style'] = f'--gcols:{cols}; grid-column-gap:{gut:g}vw; grid-row-gap:{gut:g}vw; width:auto'
    # Squarespace JS hoists nested mobile-menu folders next to the root folder
    for root in s.select('.header-menu-nav-folder[data-folder="root"]'):
        for sub in root.select('.header-menu-nav-folder'):
            root.insert_after(sub.extract())
    ends = {e['slug']: e['end_utc'] for e in events}
    for it in s.select('.summary-item'):
        a = it.find('a', href=re.compile(r'^/events/'))
        if a and a['href'].split('/')[2] in ends: it['data-end'] = ends[a['href'].split('/')[2]]
    # single-candidate srcsets confuse the browser's width math; drop them
    for img in s.find_all('img', srcset=True):
        if ',' not in img['srcset']: del img['srcset']
        img.attrs.pop('data-load', None)
    for a in s.find_all('a', href=True):
        h = a['href']
        if h.startswith('http://maps.google.com'): a['href'] = 'https://' + h[7:]
        if h.startswith('http://www.google.com/calendar'): a['href'] = 'https://' + h[7:]
        m = re.match(r'^/events/([^?]+)\?format=ical$', h)
        if m: a['href'] = f'/events/{m.group(1)}.ics'
    if path == 'site-search':
        blk = s.select_one('.sqs-block-search .sqs-block-content')
        if blk:
            blk.clear()
            blk.append(BeautifulSoup('<div id="search"></div>', 'lxml').div)
            head.append(BeautifulSoup('<link rel="stylesheet" href="/pagefind/pagefind-ui.css">', 'lxml').link)
            s.body.append(BeautifulSoup('<script src="/pagefind/pagefind-ui.js"></script>', 'lxml').script)
            s.body.append(BeautifulSoup('<script>window.addEventListener("DOMContentLoaded",function(){var q=new URLSearchParams(location.search).get("q");var ui=new PagefindUI({element:"#search",showSubResults:true,showImages:false});if(q)ui.triggerSearch(q);});</script>', 'lxml').script)
    for blk in s.select('.sqs-block-map .sqs-block-content'):
        blk.clear()
        blk.append(BeautifulSoup('<iframe class="fbc-map" title="Map to Faith Baptist Church" src="https://maps.google.com/maps?q=Faith%20Baptist%20Church%2C%209230%20Ridge%20Road%2C%20New%20Port%20Richey%2C%20FL%2034654&amp;z=12&amp;output=embed" loading="lazy" referrerpolicy="no-referrer-when-downgrade" style="border:0;width:100%;height:100%;min-height:300px;display:block" allowfullscreen></iframe>', 'lxml').iframe)
    # header/footer are not useful search results
    for sel in ('header', 'footer', '#header', '#footer-sections'):
        for el in s.select(sel): el['data-pagefind-ignore'] = 'all'
    main = s.select_one('#sections') or s.select_one('main')
    if main and path != 'site-search': main['data-pagefind-body'] = ''
    out = str(s).replace('https://www.faithbaptistnpr.com', ROOT).replace('http://www.faithbaptistnpr.com', ROOT)
    dest = os.path.join(OUT, 'index.html' if path == 'home' else os.path.join(path, 'index.html'))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, 'w', encoding='utf-8').write(out)

# ---------- events ----------
events = json.load(open('data/events.json', encoding='utf-8'))
for e in events:
    e['s'] = dt.datetime.fromisoformat(e['start_utc'].replace('Z', '+00:00'))
    e['e'] = dt.datetime.fromisoformat(e['end_utc'].replace('Z', '+00:00'))
    e['ls'], e['le'] = e['s'].astimezone(TZ), e['e'].astimezone(TZ)
    e['multiday'] = e['ls'].date() != e['le'].date()
    # optional flags: hide_time (date only) / hide_end (start time only) when the church gives no time / end time.
    # end_utc is then only used to decide when the event has passed; it is never shown.
    e['no_time'] = bool(e.get('hide_time'))
    e['no_end'] = e['no_time'] or bool(e.get('hide_end'))
    if e['no_end']: e['multiday'] = False

def t12(d): return d.strftime('%I:%M %p').lstrip('0')
def longdate(d): return f"{d.strftime('%A, %B')} {d.day}, {d.year}"
def shortdate(d): return f"{d.strftime('%a, %b')} {d.day}, {d.year}"
def gcal(e):
    if e['no_time']: dates = f"{e['ls']:%Y%m%d}/{(e['ls'] + dt.timedelta(days=1)):%Y%m%d}"
    elif e['no_end']: dates = e['s'].strftime('%Y%m%dT%H%M%SZ') + '/' + e['s'].strftime('%Y%m%dT%H%M%SZ')
    else: dates = e['s'].strftime('%Y%m%dT%H%M%SZ') + '/' + e['e'].strftime('%Y%m%dT%H%M%SZ')
    q = {'action': 'TEMPLATE', 'text': e['title'], 'dates': dates}
    if e['location']['lines']: q['location'] = ', '.join(e['location']['lines'])
    return 'https://www.google.com/calendar/event?' + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
def maplink(e): return 'https://maps.google.com?q=' + ' '.join(e['location']['lines']) + ' '

def datetime_meta(e, kind):
    """kind: 'eventitem' or 'eventlist'"""
    fmt = longdate if kind == 'eventitem' else (shortdate if e['multiday'] else longdate)
    ls, le = e['ls'], e['le']
    if e['no_time']:
        return f'<li class="{kind}-meta-item {kind}-meta-date event-meta-item"><time class="event-date" datetime="{ls:%Y-%m-%d}">{fmt(ls)}</time></li>'
    if e['no_end']:
        return (f'<li class="{kind}-meta-item {kind}-meta-date event-meta-item"><time class="event-date" datetime="{ls:%Y-%m-%d}">{fmt(ls)}</time></li>'
                f'<li class="{kind}-meta-item {kind}-meta-time event-meta-item"><span class="event-time-localized">'
                f'<time class="event-time-localized-start" datetime="{ls:%Y-%m-%d}">{t12(ls)}</time></span></li>')
    if e['multiday']:
        sep = '<br>' if kind == 'eventitem' else ''
        return (f'<li class="{kind}-meta-item {kind}-meta-date event-meta-item"><time class="event-date" datetime="{ls:%Y-%m-%d}">{fmt(ls)}</time> '
                f'<span class="{kind}-meta-time"><time class="event-time-localized" datetime="{ls:%Y-%m-%d}">{t12(ls)}</time></span>'
                f'<span class="event-datetime-divider"></span>{sep}<time class="event-date" datetime="{le:%Y-%m-%d}">{fmt(le)}</time> '
                f'<span class="{kind}-meta-time"><time class="event-time-localized" datetime="{le:%Y-%m-%d}">{t12(le)}</time></span></li>')
    return (f'<li class="{kind}-meta-item {kind}-meta-date event-meta-item"><time class="event-date" datetime="{ls:%Y-%m-%d}">{fmt(ls)}</time></li>'
            f'<li class="{kind}-meta-item {kind}-meta-time event-meta-item"><span class="event-time-localized">'
            f'<time class="event-time-localized-start" datetime="{ls:%Y-%m-%d}">{t12(ls)}</time><span class="event-datetime-divider"></span>'
            f'<time class="event-time-localized-end" datetime="{le:%Y-%m-%d}">{t12(le)}</time></span></li>')

def export_li(e, kind):
    return (f'<li class="{kind}-meta-item {kind}-meta-export event-meta-item"><a class="{kind}-meta-export-google" href="{E_(gcal(e))}">Google Calendar</a>'
            f'<span class="{kind}-meta-export-divider"></span><a class="{kind}-meta-export-ical" href="/events/{e["slug"]}.ics">ICS</a></li>')

def list_item(e, past):
    st = 'past' if past else 'upcoming'
    cls = f'eventlist-event eventlist-event--{st}' + (' eventlist-event--hasimg eventlist-hasimg' if e['image'] else '') + (' eventlist-event--multiday' if e['multiday'] else '')
    img = ''
    if e['image']:
        w, h = (e['image_dimensions'] or 'x').split('x') if e['image_dimensions'] else ('', '')
        img = (f'<a class="eventlist-column-thumbnail content-fill" data-animation-role="image" href="/events/{e["slug"]}">'
               f'<img alt="{E_(e["title"])}" class="eventlist-thumbnail" src="{e["image"]}" width="{w}" height="{h}" loading="lazy" decoding="async" style="display:block;object-position: 50% 50%"></a>')
    end = f'<div class="eventlist-datetag-enddate">to {e["le"]:%b} {e["le"].day}</div>' if e['multiday'] else ''
    addr = ''
    if e['location']['name'] or e['location']['lines']:
        addr = f'<li class="eventlist-meta-item eventlist-meta-address event-meta-item">{E_(e["location"]["name"])} <a class="eventlist-meta-address-maplink" href="{E_(maplink(e))}" target="_blank">(map)</a></li>'
    desc = f'<div class="eventlist-description">{e["excerpt_html"]}</div>' if e['excerpt_html'] else ''
    return (f'<article class="{cls}" data-end="{e["end_utc"]}">{img}<div class="eventlist-column-date"><div class="eventlist-datetag"><div class="eventlist-datetag-inner">'
            f'<div class="eventlist-datetag-startdate eventlist-datetag-startdate--month">{e["ls"]:%b}</div>'
            f'<div class="eventlist-datetag-startdate eventlist-datetag-startdate--day">{e["ls"].day}</div>{end}<div class="eventlist-datetag-status"></div></div></div></div>'
            f'<div class="eventlist-column-info"><h1 class="eventlist-title"><a class="eventlist-title-link" href="/events/{e["slug"]}">{E_(e["title"])}</a></h1>'
            f'<ul class="eventlist-meta event-meta" data-animation-role="date">{datetime_meta(e, "eventlist")}{addr}{export_li(e, "eventlist")}</ul>{desc}'
            f'<a class="eventlist-button sqs-editable-button sqs-button-element--primary" href="/events/{e["slug"]}">View Event &#8594;</a></div></article>')

upcoming = [e for e in events if e['e'] >= NOW]
past = sorted([e for e in events if e['e'] < NOW], key=lambda e: e['s'], reverse=True)

ls_ = soup('src/templates/events-list.html')
ls_.select_one('.eventlist--upcoming').clear()
if upcoming: ls_.select_one('.eventlist--upcoming').append(BeautifulSoup(''.join(list_item(e, False) for e in upcoming), 'lxml').body)
ls_.select_one('.eventlist--past').clear()
if past: ls_.select_one('.eventlist--past').append(BeautifulSoup(''.join(list_item(e, True) for e in past), 'lxml').body)
for b in ls_.select('.eventlist > body'): b.unwrap()
finalize(ls_, 'events')

def pag_link(e, d):
    if not e: return ''
    date = f'{e["ls"]:%B} {e["ls"].day}'
    icon = ('<div class="item-pagination-icon icon icon--stroke"><svg class="caret-left-icon--small" viewBox="0 0 9 16"><polyline fill="none" stroke-miterlimit="10" points="7.3,14.7 2.5,8 7.3,1.2"></polyline></svg></div>'
            if d == 'prev' else
            '<div class="item-pagination-icon icon icon--stroke"><svg class="caret-right-icon--small" viewBox="0 0 9 16"><polyline fill="none" stroke-miterlimit="10" points="1.6,1.2 6.5,7.9 1.6,14.7"></polyline></svg></div>')
    lab = 'Previous' if d == 'prev' else 'Next'
    tag = 'span' if d == 'prev' else 'div'
    body = (f'<{tag} class="pagination-title-wrapper"><div class="visually-hidden">{lab}</div><div class="item-pagination-prev-next">{lab}</div>'
            f'<div class="events-item-pagination-date">{date}</div><h2 class="item-pagination-title">{E_(e["title"])}</h2></{tag}>')
    return f'<a class="item-pagination-link item-pagination-link--{d}" href="/events/{e["slug"]}">' + (icon + body if d == 'prev' else body + icon) + '</a>'

# item pagination: "prev" (left) is the earlier event, "next" the later one
order = sorted(events, key=lambda e: e['s'], reverse=True)
def ics_escape(t): return t.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
for i, e in enumerate(order):
    s = soup('src/templates/event-item.html')
    prev = order[i + 1] if i + 1 < len(order) else None   # earlier event (left)
    nxt = order[i - 1] if i > 0 else None                  # later event (right)
    loc = ''
    if e['location']['name'] or e['location']['lines']:
        lines = ''.join(f'<span class="eventitem-meta-address-line">{E_(l)}</span>' for l in e['location']['lines'])
        nm = f'<span class="eventitem-meta-address-line eventitem-meta-address-line--title">{E_(e["location"]["name"])}</span>' if e['location']['name'] else ''
        loc = (f'<ul class="eventitem-meta event-meta event-meta-address-container" data-content-field="location"><li class="eventitem-meta-item eventitem-meta-address">'
               f'{nm}{lines} <a class="eventitem-meta-address-maplink" href="{E_(maplink(e))}" target="_blank">(map)</a></li></ul>')
    art = (f'<article class="eventitem" id="article-{e["slug"]}">' + (f'<img class="fbc-event-img" src="{e["image"]}" loading="eager" alt="{E_(e["title"])} at Faith Baptist Church">' if e['image'] else '') + f'<div class="eventitem-column-meta"><h1 class="eventitem-title" data-content-field="title">{E_(e["title"])}</h1>'
           f'<ul class="eventitem-meta event-meta event-meta-date-time-container" data-content-field="event-date-time-range">{datetime_meta(e, "eventitem")}</ul>{loc}'
           f'<ul class="eventitem-meta event-meta event-meta-addtocalendar-container">{export_li(e, "eventitem")}</ul></div>'
           f'<div class="eventitem-column-content">{e["body_html"]}</div><div class="clear"></div></article>')
    pag = ''
    if prev or nxt:
        pag = f'<section class="item-pagination item-pagination--prev-next" data-collection-type="events-stacked" id="itemPagination">{pag_link(prev, "prev")}{pag_link(nxt, "next")}</section>'
    host = s.select_one('.sqs-events-collection-item')
    host.clear()
    host.append(BeautifulSoup('<a href="/events" class="eventitem-backlink">Back to All Events</a>' + art + pag, 'lxml').body)
    host.body.unwrap()
    t = f'{e["title"]} — Faith Baptist Church'
    s.title.string = t
    url = f'{ROOT}/events/{e["slug"]}'
    for m in s.find_all('meta'):
        k = m.get('property') or m.get('itemprop') or m.get('name')
        if k in ('og:title', 'twitter:title', 'name'): m['content'] = t
        elif k in ('og:url', 'twitter:url', 'url'): m['content'] = url
        elif k in ('og:description', 'twitter:description', 'description') and m.get('content'): m['content'] = e['description']
        elif k in ('og:image', 'twitter:image', 'thumbnailUrl', 'image') and e.get('og_image'): m['content'] = e['og_image']
    c = s.find('link', rel='canonical')
    if c: c['href'] = url
    finalize(s, f'events/{e["slug"]}')
    loc_txt = ', '.join(e['location']['lines'])
    ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Faith Baptist Church//Events//EN', 'BEGIN:VEVENT',
           f'UID:{e["slug"]}@faithbaptistnpr.com', f'DTSTAMP:{e["s"]:%Y%m%dT%H%M%SZ}'] + ([f'DTSTART;VALUE=DATE:{e["ls"]:%Y%m%d}'] if e['no_time'] else [f'DTSTART:{e["s"]:%Y%m%dT%H%M%SZ}']) + ([] if e['no_end'] else [f'DTEND:{e["e"]:%Y%m%dT%H%M%SZ}']) + [
           f'SUMMARY:{ics_escape(e["title"])}', f'URL:{url}'] + ([f'LOCATION:{ics_escape(loc_txt)}'] if loc_txt else []) + ['END:VEVENT', 'END:VCALENDAR']
    open(os.path.join(OUT, 'events', f'{e["slug"]}.ics'), 'w').write('\r\n'.join(ics) + '\r\n')

# ---------- regular pages ----------
pages = []
for f in sorted(glob.glob('src/pages/**/*.html', recursive=True)):
    path = os.path.relpath(f, 'src/pages')[:-5]
    if path == 'events' or path.startswith('events/'): continue
    pages.append(path)
    finalize(soup(f), path)

# ---------- sitemap ----------
# Removed Nov 5, 2026 (Rob): keep faithbaptistnpr.com out of Google.
# No sitemap.xml is generated any more; robots.txt disallows all crawling.
print('built', len(pages) + 1 + len(events), 'pages')

# ---- scrub every remaining Squarespace / Typekit reference ----
import re as _re
_MISS = []
_IMG = os.listdir(os.path.join(OUT, 'assets', 'img'))
def _local_img(m):
    name = _re.sub(r'[?#].*', '', m.group(0)).rsplit('/', 1)[-1].lower()
    name = _re.sub(r'\+', '-', name)
    for f in _IMG:
        if f.split('-', 1)[-1].lower() == name: return '/assets/img/' + f
    _MISS.append(m.group(0)); return ''
_PAT = r'(?:https?:)?//[a-z0-9.-]*(?:squarespace|sqspcdn|typekit)[a-z0-9.-]*\.(?:com|net)[^\s"\'<>)\]]*'
def scrub(t):
    t = _re.sub(r'https://study\.faithbaptistnpr\.com/squarespace/([^"\'\s)?]+)(\?v=\d+)?', lambda m: '/assets/ext/' + m.group(1).replace('/', '-'), t)
    t = _re.sub(r'<style[^>]*>(?:(?!</style>).)*?(?:squarespace|typekit)(?:(?!</style>).)*?</style>', '', t, flags=_re.S)
    t = _re.sub(r'<link[^>]*(?:squarespace|sqspcdn|typekit)[^>]*>', '', t)
    t = _re.sub(r'<script[^>]*src="[^"]*(?:squarespace|sqspcdn|typekit)[^"]*"[^>]*>\s*</script>', '', t)
    t = _re.sub(r'\sdata-block-(?:css|scripts)=(\'[^\']*\'|"[^"]*")', '', t)
    return _re.sub(_PAT, _local_img, t)
for dp, _, fs in os.walk(OUT):
    for f in fs:
        if f.endswith(('.html', '.xml', '.ics', '.json', '.css', '.js', '.txt')):
            p = os.path.join(dp, f); t = open(p, encoding='utf-8').read(); n = scrub(t)
            if n != t: open(p, 'w', encoding='utf-8').write(n)
print('unmatched squarespace urls:', len(_MISS), sorted(set(_MISS))[:10])
