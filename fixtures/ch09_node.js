// Chapter 9 parser differential helper: base64 lines in, view of JS JSON.parse out.
const rl = require('readline').createInterface({ input: process.stdin });
rl.on('line', l => {
  const t = Buffer.from(l, 'base64').toString('utf8');
  try { const o = JSON.parse(t); if (o === null || typeof o !== 'object' || Array.isArray(o)) { console.log('null'); return; }
    console.log(JSON.stringify([o.invoice_id === undefined ? null : String(o.invoice_id), o.payee_id === undefined ? null : String(o.payee_id), o.amount_cents === undefined ? null : String(o.amount_cents)])); }
  catch (e) { console.log('null'); }
});
