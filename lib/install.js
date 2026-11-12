'use strict';

// Shared installer for all skill-set bins. Invoked by bin/<set>.js wrappers.
// Copies sets/<set>/<skill-folder> -> <project-root>/.agents/skills/<skill-folder>
// and maintains .agents/skills-manifest.json for upgrade/uninstall bookkeeping.

const fs = require('fs');
const path = require('path');

const SET_HINTS = {
  cdo: 'Invoke the `cdo-setup` skill to configure the delivery org (requires a git repo and an official BMAD install at _bmad/config.yaml).',
  srm: 'Invoke the `srm-setup` skill, then `srm-sync` to map external skill repos.',
  scaffold: 'Invoke the `project-greenfield-scaffold` skill to stand up a new project.',
};

const EXCLUDE = /(__pycache__|\.DS_Store|Thumbs\.db|\.analysis|\.memlog\.md)|\.pyc$/;

function findProjectRoot(start) {
  let dir = path.resolve(start);
  for (;;) {
    if (fs.existsSync(path.join(dir, '.git'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return path.resolve(start);
    dir = parent;
  }
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dir') args.dir = argv[++i];
    else if (a === '--list') args.list = true;
    else if (a === '--uninstall') args.uninstall = true;
    else if (a === '--dry-run') args.dryRun = true;
    else args._.push(a);
  }
  return args;
}

function manifestPath(root) {
  return path.join(root, '.agents', 'skills-manifest.json');
}

function readManifest(root) {
  try {
    return JSON.parse(fs.readFileSync(manifestPath(root), 'utf8'));
  } catch {
    return { version: 1, sets: {} };
  }
}

function writeManifest(root, manifest) {
  fs.mkdirSync(path.dirname(manifestPath(root)), { recursive: true });
  fs.writeFileSync(manifestPath(root), JSON.stringify(manifest, null, 2) + '\n');
}

function listSkills(setDir) {
  if (!fs.existsSync(setDir)) return [];
  return fs
    .readdirSync(setDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
}

function install(setName, pkgRoot, args) {
  const setDir = path.join(pkgRoot, 'sets', setName);
  const skills = listSkills(setDir);
  if (!skills.length) {
    console.error(`error: set "${setName}" is empty or missing at ${setDir}`);
    process.exit(1);
  }

  const root = args.dir ? path.resolve(args.dir) : findProjectRoot(process.cwd());
  const targetBase = path.join(root, '.agents', 'skills');
  const manifest = readManifest(root);
  const pkgVersion = require(path.join(pkgRoot, 'package.json')).version;

  if (args.uninstall) {
    const entry = manifest.sets[setName];
    if (!entry) {
      console.log(`${setName}: not installed in ${root}`);
      return;
    }
    for (const skill of entry.skills) {
      const p = path.join(targetBase, skill);
      if (fs.existsSync(p)) {
        if (!args.dryRun) fs.rmSync(p, { recursive: true });
        console.log(`removed  ${skill}`);
      }
    }
    if (!args.dryRun) {
      delete manifest.sets[setName];
      writeManifest(root, manifest);
    }
    console.log(`${setName}: uninstalled from ${targetBase}${args.dryRun ? ' (dry run)' : ''}`);
    return;
  }

  const prior = new Set((manifest.sets[setName] && manifest.sets[setName].skills) || []);
  let created = 0;
  let updated = 0;

  if (!args.dryRun) fs.mkdirSync(targetBase, { recursive: true });

  for (const skill of skills) {
    const src = path.join(setDir, skill);
    const dest = path.join(targetBase, skill);
    const existed = fs.existsSync(dest);
    if (!args.dryRun) {
      fs.cpSync(src, dest, {
        recursive: true,
        filter: (p) => !EXCLUDE.test(path.basename(p)),
      });
    }
    existed || prior.has(skill) ? updated++ : created++;
    console.log(`${existed ? 'updated ' : 'created'}  ${skill}`);
  }

  // prune skills removed upstream since last install
  for (const gone of prior) {
    if (!skills.includes(gone)) {
      const p = path.join(targetBase, gone);
      if (fs.existsSync(p) && !args.dryRun) fs.rmSync(p, { recursive: true });
      console.log(`pruned   ${gone} (removed upstream)`);
    }
  }

  if (!args.dryRun) {
    manifest.sets[setName] = {
      package: 'skills',
      version: pkgVersion,
      source: 'github:AfiqRosli/skills',
      installedAt: new Date().toISOString(),
      skills,
    };
    writeManifest(root, manifest);
  }

  console.log(
    `\n${setName}: ${skills.length} skills -> ${targetBase}` +
      ` (${created} new, ${updated} updated)${args.dryRun ? ' [dry run]' : ''}`
  );
  if (SET_HINTS[setName]) console.log(`\nNext: ${SET_HINTS[setName]}`);
}

function run(setName) {
  const pkgRoot = path.resolve(__dirname, '..');
  const args = parseArgs(process.argv.slice(2));
  if (args.list) {
    const skills = listSkills(path.join(pkgRoot, 'sets', setName));
    console.log(`${setName} ships ${skills.length} skills:`);
    for (const s of skills) console.log(`  ${s}`);
    return;
  }
  install(setName, pkgRoot, args);
}

module.exports = { run };
