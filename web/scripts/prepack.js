#!/usr/bin/env node
/*
 * Runs after `vite build` but before `npm pack`/`npm publish`.
 *
 * Vite copies the entire `public/` directory wholesale into `dist/`. That's
 * convenient for local dev (e.g. dropping CSVs into `public/data/` so the
 * SPA can fetch them at `./data/...`), but those local artifacts must not
 * leak into the published npm tarball.
 *
 * We strip a small allowlist of known-private paths here. Anything legit
 * the SPA needs (config.json, icons, hashed assets/, index.html) stays.
 */
import { rmSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(__dirname, '..', 'dist');

const STRIP = [
  'data',         // local CSVs/TSVs from web/public/data
  '.DS_Store',    // macOS Finder droppings
  'config.local.json', // gitignored dev override
];

for (const rel of STRIP) {
  const p = join(DIST, rel);
  if (existsSync(p)) {
    rmSync(p, { recursive: true, force: true });
    console.log(`prepack: removed dist/${rel}`);
  }
}
