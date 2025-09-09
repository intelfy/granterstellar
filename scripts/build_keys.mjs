#!/usr/bin/env node
// Generate web/src/keys.generated.ts from locales/en.yml
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import yaml from 'js-yaml';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');
const localePath = resolve(root, 'locales', 'en.yml');
const webSrc = resolve(root, 'web', 'src');
const outFile = resolve(webSrc, 'keys.generated.ts');

function flatten(prefix, obj, out) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      flatten(key, v, out);
    } else {
      out[key] = String(v);
    }
  }
}

const raw = yaml.load(readFileSync(localePath, 'utf8')) || {};
const flat = {};
if (typeof raw === 'object') flatten('', raw, flat);

const keysEntries = Object.entries(flat)
  .sort((a, b) => a[0].localeCompare(b[0]))
  .map(([k, v]) => `  '${k}': ${JSON.stringify(v)},`)
  .join('\n');

const file = `/** AUTO-GENERATED: DO NOT EDIT. Source: locales/en.yml */\nexport const KEYS = {\n${keysEntries}\n} as const;\n\nexport type Key = keyof typeof KEYS;\n\n/**
 * Translate a key. If the key is unexpectedly missing (should not happen if generated),
 * returns the key string itself to avoid runtime crashes.
 * Supports simple {placeholder} interpolation.
 */\nexport function t(key: Key | string, params?: Record<string, string | number>): string {\n  if (!(key in KEYS)) return String(key);\n  let msg = KEYS[key as Key];\n  if (!params) return msg;\n  return msg.replace(/\\{(\\w+)\\}/g, (_, p) => (p in params ? String(params[p]) : '{' + p + '}'));\n}\n`;

writeFileSync(outFile, file);
console.log(`Generated ${outFile} (${Object.keys(flat).length} keys)`);
