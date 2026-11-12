#!/usr/bin/env node
// Cut a release: bump version, commit all changes, tag, then print the push.
// Usage: node tools/release.mjs [patch|minor|major] ["release notes"]

import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pkgPath = path.join(pkgRoot, 'package.json');
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));

const bump = process.argv[2] || 'patch';
const notes = process.argv[3] || '';

const [major, minor, patch] = pkg.version.split('.').map(Number);
const next =
  bump === 'major' ? `${major + 1}.0.0`
  : bump === 'minor' ? `${major}.${minor + 1}.0`
  : `${major}.${minor}.${patch + 1}`;

pkg.version = next;
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');

const run = (cmd) => execSync(cmd, { cwd: pkgRoot, stdio: 'inherit' });
run('git add -A');
try {
  run(`git commit -m "release: v${next}${notes ? ' — ' + notes : ''}"`);
} catch {
  console.log('nothing to commit — tagging anyway');
}
run(`git tag -f v${next}`);

console.log(`\nv${next} tagged. Push when ready:`);
console.log('  git push --follow-tags origin main');
