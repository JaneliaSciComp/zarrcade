#!/usr/bin/env node
/*
 * @janelia/zarrcade CLI — scaffolds a deployable Zarrcade site by copying
 * the package's prebuilt dist/ into a target directory and dropping a
 * starter config.json that the user edits before deploying.
 *
 * Usage:
 *   npx @janelia/zarrcade init <target-dir>   # scaffold a new site
 *   npx @janelia/zarrcade --version
 *   npx @janelia/zarrcade --help
 *
 * Implementation notes: we deliberately keep this script dependency-free
 * (Node builtins only) so the published package can declare zero runtime
 * dependencies and `npx` invocations stay fast.
 */

import { readFileSync, existsSync, readdirSync, cpSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PACKAGE_ROOT = resolve(__dirname, '..');
const DIST_DIR = join(PACKAGE_ROOT, 'dist');

function readPackageJson() {
  const text = readFileSync(join(PACKAGE_ROOT, 'package.json'), 'utf8');
  return JSON.parse(text);
}

const HELP = `\
Usage: zarrcade <command> [options]

Commands:
  init <target>     Scaffold a new Zarrcade site in <target>. Copies the
                    prebuilt SPA and writes a starter config.json that you
                    edit before deploying.

Options:
  -h, --help        Show this help.
  -v, --version     Print the installed version.

Examples:
  npx @janelia/zarrcade init my-gallery
  cd my-gallery
  $EDITOR config.json     # set dataUrl, title, filters, etc.
  # then upload the directory to any static host (S3, GitHub Pages, nginx).
`;

const STARTER_CONFIG = {
  dataUrl: '',
  title: 'My Zarrcade Gallery',
  data: {
    delimiter: ',',
    pathColumn: 'path',
  },
  display: {
    pageSize: 50,
  },
  filters: [],
  viewers: [
    {
      name: 'Neuroglancer',
      icon: 'neuroglancer.png',
      urlTemplate:
        'https://neuroglancer-demo.appspot.com/#!{"layers":[{"name":"{NAME}","source":"{URL}","type":"auto"}],"selectedLayer":{"visible":true,"layer":"{NAME}"},"layout":"4panel-alt"}',
      enabled: true,
    },
    {
      name: 'Avivator',
      icon: 'vizarr_logo.png',
      urlTemplate: 'https://janeliascicomp.github.io/viv/?image_url={ENCODED_URL}',
      enabled: true,
    },
  ],
};

function die(msg, code = 1) {
  console.error(`zarrcade: ${msg}`);
  process.exit(code);
}

function commandInit(args) {
  const target = args[0];
  if (!target) die('init requires a target directory.\n\n' + HELP, 2);

  const targetAbs = resolve(process.cwd(), target);
  if (existsSync(targetAbs) && readdirSync(targetAbs).length > 0) {
    die(`refusing to scaffold into "${target}": directory is not empty.`);
  }

  if (!existsSync(DIST_DIR)) {
    die(
      `internal error: prebuilt dist/ is missing from this package install at ${DIST_DIR}.\n` +
        'This usually means the package was published incorrectly. Please file an issue.',
    );
  }

  // Copy the prebuilt SPA into the target.
  cpSync(DIST_DIR, targetAbs, { recursive: true });

  // Write a starter config.json next to index.html. The shipped dist already
  // contains a default config.json (empty dataUrl → Welcome screen), but we
  // overwrite it with one carrying a friendlier placeholder title so the
  // user sees their edits land somewhere obvious.
  writeFileSync(
    join(targetAbs, 'config.json'),
    JSON.stringify(STARTER_CONFIG, null, 2) + '\n',
    'utf8',
  );

  console.log(`Scaffolded a Zarrcade site at ${targetAbs}`);
  console.log('');
  console.log('Next steps:');
  console.log(`  1. Edit ${join(target, 'config.json')} — set "dataUrl" to your CSV/TSV.`);
  console.log(`  2. Preview locally: npx serve ${target}  (or any static file server)`);
  console.log(`  3. Deploy the directory to your static host (S3, GitHub Pages, nginx, etc.).`);
  console.log('');
  console.log('Docs: https://github.com/JaneliaSciComp/zarrcade');
}

function main(argv) {
  const args = argv.slice(2);
  if (args.length === 0 || args[0] === '-h' || args[0] === '--help' || args[0] === 'help') {
    console.log(HELP);
    return;
  }
  if (args[0] === '-v' || args[0] === '--version') {
    console.log(readPackageJson().version);
    return;
  }
  const [command, ...rest] = args;
  switch (command) {
    case 'init':
      commandInit(rest);
      return;
    default:
      die(`unknown command "${command}".\n\n${HELP}`, 2);
  }
}

main(process.argv);
