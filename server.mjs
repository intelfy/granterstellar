#!/usr/bin/env node
import http from 'node:http';
import https from 'node:https';
import { readFile, stat } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { URL } from 'node:url';

const ROOT = new URL('.', import.meta.url).pathname;
// Load .env (no deps) if present
async function loadDotEnv() {
  try {
    const envPath = join(ROOT, '.env');
    const txt = await readFile(envPath, 'utf-8');
    for (const line of txt.split(/\r?\n/)) {
      if (!line || line.trim().startsWith('#')) continue;
      const idx = line.indexOf('=');
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      const val = line.slice(idx + 1).trim().replace(/^"|"$/g, '');
      if (!(key in process.env)) process.env[key] = val;
    }
  } catch {}
}

await loadDotEnv();

const PORT = Number(process.env.PORT || 5173);
const MAILGUN_DOMAIN = process.env.MAILGUN_DOMAIN || '';
const MAILGUN_API_KEY = process.env.MAILGUN_API_KEY || '';
const MAILGUN_LIST = process.env.MAILGUN_LIST || ''; // e.g., waitlist@mg.example.com
const MAILGUN_API_HOST = process.env.MAILGUN_API_HOST || 'api.mailgun.net'; // set to api.eu.mailgun.net for EU regions


const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
  '.svg': 'image/svg+xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

function sendJson(res, code, obj) {
  const body = Buffer.from(JSON.stringify(obj));
  setSecurityHeaders(res);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': String(body.length),
  });
  res.end(body);
}

function basicAuth(user, pass) {
  return 'Basic ' + Buffer.from(`${user}:${pass}`).toString('base64');
}

async function addToMailingList(email, opts = {}) {
  if (!MAILGUN_API_KEY || !MAILGUN_DOMAIN) throw new Error('Mailgun not configured');
  // Prefer mailing list if provided, else store as route that triggers stored recipient
  const hasList = Boolean(MAILGUN_LIST);
  const path = hasList
    ? `/v3/lists/${encodeURIComponent(MAILGUN_LIST)}/members`
    : `/v3/${encodeURIComponent(MAILGUN_DOMAIN)}/messages`;

  const postData = new URLSearchParams(
    hasList
      ? { address: email, subscribed: opts.subscribed ?? 'no', upsert: 'yes', vars: JSON.stringify(opts.vars || {}) }
      : { from: `Waitlist <mailgun@${MAILGUN_DOMAIN}>`, to: email, subject: 'Granterstellar waitlist', text: 'Thanks for joining!' }
  ).toString();

  const options = {
    hostname: MAILGUN_API_HOST,
    port: 443,
    path,
    method: 'POST',
    headers: {
      Authorization: basicAuth('api', MAILGUN_API_KEY),
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(postData),
    },
  };

  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      const chunks = [];
      res.on('data', (d) => chunks.push(d));
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf-8');
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ ok: true, status: res.statusCode, body });
        } else {
          reject(new Error(`Mailgun error ${res.statusCode}: ${body}`));
        }
      });
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

function serveFile(req, res, filePath) {
  const ext = extname(filePath);
  const type = CONTENT_TYPES[ext] || 'application/octet-stream';
  createReadStream(filePath)
    .on('error', () => sendJson(res, 404, { error: 'Not found' }))
    .once('open', () => {
      setSecurityHeaders(res);
      res.writeHead(200, { 'Content-Type': type });
    })
    .pipe(res);
}

// Simple in-memory rate limit: max N per IP per window
const RATE_LIMIT_WINDOW_MS = 5 * 60 * 1000; // 5 minutes
const RATE_LIMIT_MAX = 10;
const RATE = new Map(); // ip -> [timestamps]

function checkRate(ip) {
  const now = Date.now();
  const arr = RATE.get(ip) || [];
  const recent = arr.filter((t) => now - t < RATE_LIMIT_WINDOW_MS);
  if (recent.length >= RATE_LIMIT_MAX) return false;
  recent.push(now);
  RATE.set(ip, recent);
  return true;
}

async function handle(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === 'POST' && url.pathname === '/api/waitlist') {
    const ip = req.headers['x-forwarded-for']?.toString().split(',')[0].trim() || req.socket.remoteAddress || 'unknown';
    if (!checkRate(ip)) return sendJson(res, 429, { error: 'Too many requests' });
    let body = '';
    req.on('data', (chunk) => (body += chunk));
  req.on('end', async () => {
      try {
        const data = JSON.parse(body || '{}');
        const email = String((data.email || '').trim().toLowerCase());
        const hp = String((data.hp || '').trim());
        if (hp) return sendJson(res, 200, { ok: true }); // silently ignore bots
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
          return sendJson(res, 400, { error: 'Invalid email' });
        }
        // Double opt-in: add as unsubscribed with a token and send confirmation email with link
        const token = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
        const confirmBase = process.env.PUBLIC_BASE_URL || `http://localhost:${PORT}`;
        const confirmLink = `${confirmBase}/confirm?email=${encodeURIComponent(email)}&token=${encodeURIComponent(token)}`;

        // Store token in Mailgun member vars; member is unsubscribed (no)
        await addToMailingList(email, { subscribed: 'no', vars: { token } });

        // Send confirmation email
        await sendMail(email, 'Confirm your Granterstellar waitlist subscription', `Please confirm your email by visiting: ${confirmLink}\n\nIf you didn't request this, ignore this email.`);
        return sendJson(res, 200, { ok: true, pending: true });
      } catch (e) {
        console.error('[waitlist] Error handling request:', e?.message || e, e?.stack || '');
        return sendJson(res, 500, { error: 'Server error' });
      }
    });
    return;
  }

  // Confirm subscription
  if (req.method === 'GET' && url.pathname === '/confirm') {
    const email = String((url.searchParams.get('email') || '').toLowerCase());
    const token = String(url.searchParams.get('token') || '');
    if (!email || !token) return sendJson(res, 400, { error: 'Missing parameters' });
    try {
      const ok = await confirmMember(email, token);
      if (ok) {
        // Serve a simple static page if present
        const success = join(ROOT, 'confirmed.html');
        try { await stat(success); return serveFile(req, res, success); } catch {}
        return sendJson(res, 200, { ok: true });
      }
      return sendJson(res, 400, { error: 'Invalid token' });
    } catch (e) {
      console.error('[confirm] Error confirming subscription:', e?.message || e, e?.stack || '');
      return sendJson(res, 500, { error: 'Server error' });
    }
  }

  // Explicit robots.txt content-type
  if (req.method === 'GET' && url.pathname === '/robots.txt') {
    const filePath = join(ROOT, 'robots.txt');
    try { await stat(filePath); } catch { return sendJson(res, 404, { error: 'Not found' }); }
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    setSecurityHeaders(res);
    return createReadStream(filePath).pipe(res);
  }

  // security.txt compatibility at root -> redirect to /.well-known/security.txt
  if (req.method === 'GET' && url.pathname === '/security.txt') {
    setSecurityHeaders(res);
    res.writeHead(308, { Location: '/.well-known/security.txt' });
    return res.end();
  }

  if (req.method === 'GET' && url.pathname === '/healthz') {
    setSecurityHeaders(res);
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('ok');
  }

  // static files
  let pathname = url.pathname;
  if (pathname === '/') pathname = '/index.html';
  const local = join(ROOT, normalize(pathname.replace(/^\/+/, '')));
  try {
    await stat(local);
    return serveFile(req, res, local);
  } catch {
    return sendJson(res, 404, { error: 'Not found' });
  }
}

http.createServer(handle).listen(PORT, () => {
  console.log(`Landing server running on http://localhost:${PORT}`);
});

function setSecurityHeaders(res) {
  // HSTS (browsers ignore HSTS on localhost)
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
  // CSP: tight by default. Adjust if adding analytics or external assets.
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    'upgrade-insecure-requests',
  ].join('; ');
  res.setHeader('Content-Security-Policy', csp);
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Permissions-Policy', 'accelerometer=(), camera=(), geolocation=(), microphone=(), interest-cohort=()');
  res.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
  res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
}

async function sendMail(to, subject, text) {
  if (!MAILGUN_API_KEY || !MAILGUN_DOMAIN) throw new Error('Mailgun not configured');
  const postData = new URLSearchParams({
    from: `Granterstellar <mailgun@${MAILGUN_DOMAIN}>`,
    to,
    subject,
    text,
  }).toString();
  const options = {
  hostname: MAILGUN_API_HOST,
    port: 443,
    path: `/v3/${encodeURIComponent(MAILGUN_DOMAIN)}/messages`,
    method: 'POST',
    headers: {
      Authorization: basicAuth('api', MAILGUN_API_KEY),
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(postData),
    },
  };
  await new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      res.on('data', () => {});
      res.on('end', resolve);
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function confirmMember(email, token) {
  // Fetch member to verify token, then set subscribed=yes if matches
  if (!MAILGUN_LIST) throw new Error('MAILGUN_LIST is required for double opt-in');
  const getOptions = {
  hostname: MAILGUN_API_HOST,
    port: 443,
    path: `/v3/lists/${encodeURIComponent(MAILGUN_LIST)}/members/${encodeURIComponent(email)}`,
    method: 'GET',
    headers: { Authorization: basicAuth('api', MAILGUN_API_KEY) },
  };
  const member = await new Promise((resolve, reject) => {
    const req = https.request(getOptions, (res) => {
      const chunks = [];
      res.on('data', (d) => chunks.push(d));
      res.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf-8'))); } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.end();
  });
  const vars = member?.member?.vars || {};
  if (vars.token !== token) return false;

  const postData = new URLSearchParams({ subscribed: 'yes', upsert: 'yes', vars: JSON.stringify({ ...vars, token: undefined }) }).toString();
  const updOptions = {
  hostname: MAILGUN_API_HOST,
    port: 443,
    path: `/v3/lists/${encodeURIComponent(MAILGUN_LIST)}/members/${encodeURIComponent(email)}`,
    method: 'PUT',
    headers: {
      Authorization: basicAuth('api', MAILGUN_API_KEY),
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(postData),
    },
  };
  await new Promise((resolve, reject) => {
    const req = https.request(updOptions, (res) => { res.on('data', () => {}); res.on('end', resolve); });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
  return true;
}
