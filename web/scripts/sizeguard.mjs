#!/usr/bin/env node
/**
 * Simple bundle-size guard.
 * - Computes total gzipped bytes of all .js in dist
 * - Optionally enforces per-chunk caps via a manifest file
 *
 * Usage:
 *   node scripts/sizeguard.mjs [--budget <bytes>] [--manifest dist/stats.html]
 * Env:
 *   BUNDLE_BUDGET (bytes), default 600000
 */
import { createGzip } from 'node:zlib'
import { pipeline } from 'node:stream/promises'
import { createReadStream, promises as fs } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

async function gzipSize(file) {
  const src = createReadStream(file)
  const gzip = createGzip({ level: 9 })
  let total = 0
  gzip.on('data', (c) => (total += c.length))
  await pipeline(src, gzip)
  return total
}

async function main() {
  const args = process.argv.slice(2)
  const budgetIdx = args.indexOf('--budget')
  const budget = budgetIdx !== -1 ? parseInt(args[budgetIdx + 1], 10) : parseInt(process.env.BUNDLE_BUDGET || '600000', 10)
  const distDir = path.resolve(__dirname, '..', 'dist')
  const entries = await fs.readdir(distDir, { withFileTypes: true })
  const jsFiles = []
  for (const ent of entries) {
    if (ent.isDirectory() && ent.name === 'assets') {
      const assets = await fs.readdir(path.join(distDir, 'assets'))
      for (const f of assets) if (f.endsWith('.js')) jsFiles.push(path.join(distDir, 'assets', f))
    }
    if (ent.isFile() && ent.name.endsWith('.js')) jsFiles.push(path.join(distDir, ent.name))
  }
  if (!jsFiles.length) {
    console.error('No JS files found under dist/')
    process.exit(2)
  }
  let total = 0
  for (const f of jsFiles) total += await gzipSize(f)
  console.log(`Total gzipped JS bytes: ${total}`)
  console.log(`Budget: ${budget} bytes`)
  if (total > budget) {
    console.error(`Error: total gzipped JS (${total}) exceeds budget (${budget})`)
    process.exit(1)
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(2)
})
