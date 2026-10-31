// POST /api/form — receives the site's forms.
// Every submission is stored in the FORMS KV namespace (key "sub:<time>:<id>", 1-year expiry) so nothing is lost.
// If the FORM_TO secret is set (and FORM_FROM, a sender on a domain verified with Cloudflare Email Sending),
// each submission is also emailed through the SEND_EMAIL binding.
const MAX_FIELD = 5000;

export async function onRequestPost({ request, env }) {
  const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { 'content-type': 'application/json' } });
  let form;
  try { form = await request.formData(); } catch { return json({ ok: false, error: 'bad request' }, 400); }
  if ((form.get('_hp') || '').toString().trim()) return json({ ok: true }); // honeypot: pretend success for bots

  const fields = {};
  for (const [k, v] of form.entries()) {
    if (k === '_hp' || typeof v !== 'string') continue;
    fields[k] = v.slice(0, MAX_FIELD);
  }
  if (Object.keys(fields).length > 40) return json({ ok: false, error: 'too many fields' }, 400);
  const record = {
    form: fields._form || 'Form', page: fields._page || '', received: new Date().toISOString(),
    country: request.cf?.country || '', fields,
  };
  delete record.fields._form; delete record.fields._page;

  const id = crypto.randomUUID();
  const key = `sub:${record.received}:${id}`;
  let stored = false;
  if (env.FORMS) {
    await env.FORMS.put(key, JSON.stringify(record), { expirationTtl: 60 * 60 * 24 * 365, metadata: { form: record.form, emailed: false } });
    stored = true;
  }

  let emailed = false;
  if (env.FORM_TO && env.FORM_FROM && env.SEND_EMAIL) {
    try {
      const lines = Object.entries(record.fields).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join('\n');
      await env.SEND_EMAIL.send({
        to: env.FORM_TO, from: env.FORM_FROM,
        replyTo: record.fields.email || undefined,
        subject: `${record.form} — faithbaptistnpr.com`,
        text: `${lines}\n\nPage: ${record.page}\nReceived: ${record.received}`,
      });
      emailed = true;
      if (stored) await env.FORMS.put(key, JSON.stringify(record), { expirationTtl: 60 * 60 * 24 * 365, metadata: { form: record.form, emailed: true } });
    } catch (e) { console.log('email failed', e && e.message); }
  }
  if (!stored && !emailed) return json({ ok: false, error: 'not stored' }, 500);
  return json({ ok: true });
}

export const onRequest = () => new Response('Method Not Allowed', { status: 405, headers: { allow: 'POST' } });
