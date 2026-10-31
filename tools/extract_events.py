"""One-time: extract events from mirrored Squarespace pages into data/events.json."""
import json, re, os, glob, urllib.parse
from bs4 import BeautifulSoup
lst = BeautifulSoup(open('src/pages/events.html'), 'lxml')
info = {}
for art in lst.select('.eventlist-event'):
    slug = art.select_one('.eventlist-title-link')['href'].rsplit('/', 1)[-1]
    img = art.select_one('img.eventlist-thumbnail')
    desc = art.select_one('.eventlist-description')
    info[slug] = {'image': img['src'] if img else None,
                  'image_dimensions': img.get('data-image-dimensions') if img else None,
                  'excerpt_html': desc.decode_contents().strip() if desc else ''}
events = []
for f in sorted(glob.glob('src/pages/events/*.html')):
    slug = os.path.basename(f)[:-5]
    s = BeautifulSoup(open(f), 'lxml')
    a = s.select_one('article.eventitem')
    g = a.select_one('.eventitem-meta-export-google')['href']
    q = urllib.parse.parse_qs(urllib.parse.urlparse(g).query)
    st, en = q['dates'][0].split('/')
    iso = lambda x: f'{x[0:4]}-{x[4:6]}-{x[6:8]}T{x[9:11]}:{x[11:13]}:{x[13:15]}Z'
    addr = [x.get_text(strip=True) for x in a.select('.eventitem-meta-address-line')]
    title_line = a.select_one('.eventitem-meta-address-line--title')
    og = s.find('meta', property='og:image')
    ogd = s.find('meta', property='og:description')
    events.append({
        'slug': slug,
        'title': a.select_one('.eventitem-title').get_text(),
        'start_utc': iso(st), 'end_utc': iso(en),
        'date_text': a.select_one('time.event-date').get_text(strip=True) if a.select_one('time.event-date') else '',
        'location': {'name': title_line.get_text(strip=True) if title_line else '',
                     'lines': addr[1:] if title_line else addr},
        'image': info.get(slug, {}).get('image'),
        'image_dimensions': info.get(slug, {}).get('image_dimensions'),
        'og_image': og['content'] if og else None,
        'description': ogd['content'] if ogd else '',
        'excerpt_html': info.get(slug, {}).get('excerpt_html', ''),
        'body_html': a.select_one('.eventitem-column-content').decode_contents().strip(),
    })
events.sort(key=lambda e: e['start_utc'])
os.makedirs('data', exist_ok=True)
json.dump(events, open('data/events.json', 'w'), indent=1, ensure_ascii=False)
print(len(events), [e['slug'] for e in events])
