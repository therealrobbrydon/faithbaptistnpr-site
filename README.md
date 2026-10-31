# faithbaptistnpr.com

Static rebuild of the Faith Baptist Church (New Port Richey, FL) website, hosted on Cloudflare Pages.

## Layout
- `src/pages/` – page HTML mirrored from the original site (one file per URL)
- `src/static/` – images, CSS, fonts, `site.js`, `_redirects`, `robots.txt`
- `src/templates/` – shells for the events list and event detail pages
- `data/events.json` – **events live here**; edit this file to add/change/remove events
- `functions/api/form.js` – Pages Function that receives the site's forms
- `tools/build.py` – builds everything into `public/`

## Build & preview
```sh
pip install beautifulsoup4 lxml
python3 tools/build.py && npx -y pagefind --site public
cd public && python3 -m http.server 8811
```

## Deploy
Pushing to `main` runs `.github/workflows/deploy.yml`, which builds and deploys with Wrangler.
It needs repository secrets `CLOUDFLARE_API_TOKEN` (Pages: Edit) and `CLOUDFLARE_ACCOUNT_ID`.
Manual deploy: `npx wrangler pages deploy public --project-name faithbaptistnpr-site`.

## Forms
Forms POST to `/api/form`. Every submission is stored in the KV namespace bound as `FORMS`
(key `sub:<timestamp>:<id>`, kept 1 year). Email delivery switches on once the Pages project has
`FORM_TO` / `FORM_FROM` variables and a `SEND_EMAIL` binding configured.
