#!/usr/bin/env node
// Re-stages all sets from a source repo's .agents/skills directory.
// Usage: node tools/stage.mjs --from C:\Core\Businesses\PRTO\prto
//        node tools/stage.mjs --from /path/to/repo --set cdo
//
// Wipe + copy per set: sets/<set>/ is rebuilt from the source's
// .agents/skills/<matching-dirs> so deleted skills disappear here too.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const SETS = {
  cdo: (name) => name.startsWith('cdo-'),
  srm: (name) => name.startsWith('srm-'),
  scaffold: (name) => name === 'project-greenfield-scaffold',
};

const EXCLUDE = /(__pycache__|\.DS_Store|Thumbs\.db|\.analysis|\.memlog\.md)|\.pyc$/;

const args = process.argv.slice(2);
const fromIdx = args.indexOf('--from');
const setIdx = args.indexOf('--set');
const from = fromIdx >= 0 ? path.resolve(args[fromIdx + 1]) : null;
const onlySet = setIdx >= 0 ? args[setIdx + 1] : null;

if (!from) {
  console.error('usage: node tools/stage.mjs --from <repo-root> [--set <name>]');
  process.exit(1);
}
const srcBase = path.join(from, '.agents', 'skills');
if (!fs.existsSync(srcBase)) {
  console.error(`no .agents/skills at ${srcBase}`);
  process.exit(1);
}

const all = fs
  .readdirSync(srcBase, { withFileTypes: true })
  .filter((e) => e.isDirectory())
  .map((e) => e.name);

for (const [set, match] of Object.entries(SETS)) {
  if (onlySet && set !== onlySet) continue;
  const hits = all.filter(match).sort();
  const dest = path.join(pkgRoot, 'sets', set);
  fs.rmSync(dest, { recursive: true, force: true });
  fs.mkdirSync(dest, { recursive: true });
  for (const skill of hits) {
    fs.cpSync(path.join(srcBase, skill), path.join(dest, skill), {
      recursive: true,
      filter: (p) => !EXCLUDE.test(path.basename(p)),
    });
  }
  console.log(`${set}: staged ${hits.length} skills`);
}

console.log('\nNext: bump version in package.json, commit, tag (git tag vX.Y.Z), push.');
