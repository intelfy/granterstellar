#!/usr/bin/env node
import http from 'node:http';
import https from 'node:https';
import crypto from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { createReadStream, readFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { URL } from 'node:url';

const ROOT = new URL('.', import.meta.url).pathname;
// Load .env for local dev only (NODE_ENV !== 'production')
async function loadDotEnv() {
  try {
    if (process.env.NODE_ENV === 'production') return;
    const envPath = join(ROOT, '.env');
    const txt = await readFile(envPath, 'utf-8');
    for (const line of txt.split(/\r?\n/)) {
      if (!line || line.trim().startsWith('#')) continue;
      const idx = line.indexOf('=');
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      const val = line.slice(idx + 1).trim().replace(/^\"|\"$/g, '');
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
const UMAMI_SRC = process.env.VITE_UMAMI_SRC || '';
const UMAMI_WEBSITE_ID = process.env.VITE_UMAMI_WEBSITE_ID || '';

// Strictly validate Umami script URL: require https and /script.js path
function parseUmami(u) {
  try {
    if (!u) return null;
    const url = new URL(u);
    if (url.protocol !== 'https:') return null;
    if (!/\/script\.js$/i.test(url.pathname)) return null;
    return { src: url.toString(), origin: url.origin };
  } catch {
    return null;
  }
}
const UMAMI = parseUmami(UMAMI_SRC);

// Strictly validate the website id (UUID-ish) to avoid attribute injection
function safeWebsiteId(id) {
  const s = String(id || '').trim();
  // Accept UUID v4 or a 32-36 char hex/hyphen token
  if (/^[0-9a-fA-F-]{32,36}$/.test(s)) return s;
  return '';
}

function escapeAttr(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}


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
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ ok: true, status: res.statusCode });
        } else {
          reject(new Error(`Mailgun error ${res.statusCode}`));
        }
      });
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

function serveFile(req, res, filePath, onDone) {
  const ext = extname(filePath);
  const type = CONTENT_TYPES[ext] || 'application/octet-stream';
  const stream = createReadStream(filePath)
    .on('error', (err) => {
      try { onDone && onDone(); } catch {}
      return sendJson(res, 404, { error: 'Not found' })
    })
    .once('open', () => {
      setSecurityHeaders(res);
      res.writeHead(200, { 'Content-Type': type });
    })
    .pipe(res);
  const finalize = () => { try { onDone && onDone(); } catch {} };
  stream.on('close', finalize);
  res.on('close', finalize);
}

// Simple in-memory rate limit: max N per IP per window
const RATE_LIMIT_WINDOW_MS = 5 * 60 * 1000; // 5 minutes
const RATE_LIMIT_MAX = 10; // strict for POST /api/waitlist
const RATE = new Map(); // ip -> [timestamps]

// Permissive per-IP limiter for static file GET/HEAD handling
const STATIC_RATE_LIMIT_MAX = Number(process.env.STATIC_RATE_LIMIT_MAX || 300);
const RATE_STATIC = new Map(); // ip -> [timestamps]

function checkRate(ip) {
  const now = Date.now();
  const arr = RATE.get(ip) || [];
  const recent = arr.filter((t) => now - t < RATE_LIMIT_WINDOW_MS);
  if (recent.length >= RATE_LIMIT_MAX) return false;
  recent.push(now);
  RATE.set(ip, recent);
  return true;
}

function checkRateStatic(ip) {
  const now = Date.now();
  const arr = RATE_STATIC.get(ip) || [];
  const recent = arr.filter((t) => now - t < RATE_LIMIT_WINDOW_MS);
  if (recent.length >= STATIC_RATE_LIMIT_MAX) return false;
  recent.push(now);
  RATE_STATIC.set(ip, recent);
  return true;
}

async function handle(req, res) {
  // Avoid trusting Host header blindly. Use configured PUBLIC_BASE_URL origin when valid, else localhost.
  const origin = safePublicBaseUrl(process.env.PUBLIC_BASE_URL) || `http://localhost:${PORT}`;
  const url = new URL(req.url, origin);

  if (req.method === 'POST' && url.pathname === '/api/waitlist') {
    // Simple concurrency guard to avoid overwhelming downstream services
    globalThis.__postInflight = globalThis.__postInflight || 0;
    const MAX_POST_INFLIGHT = Number(process.env.MAX_POST_INFLIGHT || 50);
    if (globalThis.__postInflight >= MAX_POST_INFLIGHT) {
      return sendJson(res, 503, { error: 'Busy, try again' });
    }
    globalThis.__postInflight += 1;
    const ip = req.headers['x-forwarded-for']?.toString().split(',')[0].trim() || req.socket.remoteAddress || 'unknown';
    if (!checkRate(ip)) return sendJson(res, 429, { error: 'Too many requests' });
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > 10 * 1024) { // 10KB limit
        res.writeHead(413, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ error: 'Payload too large' }));
        try { req.destroy(); } catch {}
      }
    });
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
  // Stronger token (random UUID-ish string)
  const token = cryptoRandom();
        // In production, do not fall back to cleartext. If PUBLIC_BASE_URL is missing/invalid in prod,
        // use a non-routable https origin to avoid accidental cleartext links.
        const confirmBase = (process.env.NODE_ENV === 'production')
          ? (safePublicBaseUrl(process.env.PUBLIC_BASE_URL) || 'https://example.invalid')
          : (safePublicBaseUrl(process.env.PUBLIC_BASE_URL) || `http://localhost:${PORT}`);
        const confirmLink = `${confirmBase}/confirm?email=${encodeURIComponent(email)}&token=${encodeURIComponent(token)}`;

        // Store token in Mailgun member vars; member is unsubscribed (no)
        await addToMailingList(email, { subscribed: 'no', vars: { token } });

        // Send confirmation email
        await sendMail(email, 'Confirm your Granterstellar waitlist subscription', `Please confirm your email by visiting: ${confirmLink}\n\nIf you didn't request this, ignore this email.`);
    return sendJson(res, 200, { ok: true, pending: true });
      } catch (e) {
        logError('[waitlist] Error handling request', e);
        return sendJson(res, 500, { error: 'Server error' });
      }
  });
  res.on('close', () => { globalThis.__postInflight = Math.max(0, (globalThis.__postInflight || 0) - 1); });
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
      logError('[confirm] Error confirming subscription', e);
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
  // Apply a permissive rate limit for static file requests
  if (req.method === 'GET' || req.method === 'HEAD') {
    const ip = req.headers['x-forwarded-for']?.toString().split(',')[0].trim() || req.socket.remoteAddress || 'unknown';
    if (!checkRateStatic(ip)) {
      return sendJson(res, 429, { error: 'Too many requests' });
    }
  }
  const local = safeLocalPath(pathname);
  // Lightweight FS concurrency guard to reduce resource exhaustion risk
  const MAX_FS_CONCURRENCY = Number(process.env.STATIC_FS_CONCURRENCY || 50);
  globalThis.__fsInflight = globalThis.__fsInflight || 0;
  const acquireFsSlot = () => {
    if (globalThis.__fsInflight >= MAX_FS_CONCURRENCY) return false;
    globalThis.__fsInflight += 1; return true;
  };
  const releaseFsSlot = () => { globalThis.__fsInflight = Math.max(0, (globalThis.__fsInflight || 0) - 1); };
  if (!acquireFsSlot()) return sendJson(res, 503, { error: 'Busy, try again' });
  try {
    await stat(local);
    // Inject Umami into landing index.html when configured
  if (local.endsWith('/index.html') && UMAMI) {
      try {
        let html = await readFile(local, 'utf-8');
        if (html) {
          const websiteId = safeWebsiteId(UMAMI_WEBSITE_ID);
          // Skip injection if website id isn't valid
          if (!websiteId) {
            setSecurityHeaders(res);
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            const out = res.end(html);
            releaseFsSlot();
            return out;
          }
          const marker = '</head>';
          // Insert strictly-sanitized analytics tag: both src and attributes escaped
          const tag = `\n  <script async src="${escapeAttr(UMAMI.src)}" data-website-id="${escapeAttr(websiteId)}"></script>\n`;
          if (!html.includes('data-website-id')) {
            html = html.replace(marker, `${tag}${marker}`);
          }
          setSecurityHeaders(res);
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          const out = res.end(html);
          releaseFsSlot();
          return out;
        }
      } catch {}
    }
    return serveFile(req, res, local, releaseFsSlot);
  } catch {
    releaseFsSlot();
    return sendJson(res, 404, { error: 'Not found' });
  }
}

// Prefer HTTPS when cert/key provided (useful outside Traefik). Otherwise bind HTTP (dev/local only).
const HTTPS_KEY_PATH = process.env.HTTPS_KEY_PATH;
const HTTPS_CERT_PATH = process.env.HTTPS_CERT_PATH;
if (process.env.ENABLE_HTTPS === '1' && HTTPS_KEY_PATH && HTTPS_CERT_PATH) {
  try {
    const key = readFileSync(HTTPS_KEY_PATH);
    const cert = readFileSync(HTTPS_CERT_PATH);
    https.createServer({ key, cert }, handle).listen(PORT, () => {
      console.log(`Landing server running (HTTPS) on port ${PORT}`);
    });
  } catch (e) {
    console.error('Failed to start HTTPS server, falling back to HTTP:', e && e.message);
    http.createServer(handle).listen(PORT, () => {
      console.log(`Landing server running on http://localhost:${PORT}`);
    });
  }
} else {
  // In production, refuse to start plain HTTP to avoid cleartext traffic; rely on external HTTPS termination.
    const allowPlainHttp = process.env.ALLOW_HTTP_IN_PROD === '1';
    if (process.env.NODE_ENV === 'production' && !allowPlainHttp) {
      console.error('Refusing to start HTTP server in production without ENABLE_HTTPS=1 (or ALLOW_HTTP_IN_PROD=1 when behind a proxy)');
      process.exit(1);
    }
  // Note: HTTPS is typically terminated by Traefik/Coolify in deployment; local dev can use HTTP.
  http.createServer(handle).listen(PORT, () => {
    console.log(`Landing server running on http://localhost:${PORT}`);
  });
}

function setSecurityHeaders(res) {
  // HSTS (browsers ignore HSTS on localhost)
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
  // CSP: tight by default. Adjust if adding analytics or external assets.
  const umamiOrigin = UMAMI?.origin || '';
  const scriptSrc = ["'self'"].concat(umamiOrigin ? [umamiOrigin] : []);
  const connectSrc = ["'self'"].concat(umamiOrigin ? [umamiOrigin] : []);
  const csp = [
    "default-src 'self'",
    `script-src ${scriptSrc.join(' ')}`,
    "style-src 'self'",
    "object-src 'none'",
    "frame-src 'none'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src ${connectSrc.join(' ')}`,
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

function safeLocalPath(requestPath) {
  // Normalize and resolve against ROOT, then ensure it stays under ROOT
  const normalized = normalize(requestPath);
  const full = resolve(ROOT, '.' + normalized);
  if (!full.startsWith(resolve(ROOT))) {
    return resolve(ROOT, 'index.html');
  }
  return full;
}

function cryptoRandom() {
  // Prefer crypto.randomUUID if available, else fallback to crypto.getRandomValues
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replace(/-/g, '');
  return crypto.randomBytes(16).toString('hex');
}

function safePublicBaseUrl(u) {
  try {
    if (!u) return '';
    const parsed = new URL(u);
    if (parsed.protocol !== 'https:') return '';
    return parsed.origin;
  } catch { return ''; }
}

function logError(prefix, err) {
  const msg = (err && err.message) ? err.message : String(err || 'unknown');
  if (process.env.NODE_ENV === 'production') {
    console.error(prefix + ':', msg);
  } else {
    console.error(prefix + ':', msg, err?.stack || '');
  }
}
