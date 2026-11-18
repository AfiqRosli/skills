'use strict';

// Shared installer for all skill-set bins. Invoked by bin/<set>.js wrappers.
// Copies sets/<set>/<skill-folder> -> <project-root>/.agents/skills/<skill-folder>
// and maintains .agents/skills-manifest.json for upgrade/uninstall bookkeeping.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const SET_HINTS = {
  cdo: 'Invoke the `cdo-setup` skill to configure the delivery org (requires a git repo and an official BMAD install at _bmad/config.yaml).',
  srm: 'Invoke the `srm-setup` skill, then `srm-sync` to map external skill repos.',
  scaffold: 'Invoke the `project-greenfield-scaffold` skill to stand up a new project.',
};

// Post-install hooks: a set whose <name>-setup skill carries a scripted
// detect->merge chain can re-run it headlessly on upgrade — repair semantics,
// stored config wins, never prompts. Fresh installs still route to the skill.
const POST_INSTALL = {
  cdo: { setupSkill: 'cdo-setup' },
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
    else if (a === '--no-setup') args.noSetup = true;
    else if (a === '--version' || a === '-V') args.version = true;
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
  } catch (e) {
    if (e.code !== 'ENOENT')
      console.warn(
        `warn: ${manifestPath(root)} unreadable (${e.message}) — existing entries will be replaced`
      );
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

  if (!args.dryRun && !args.uninstall) runPostInstall(setName, root, args);
  else if (SET_HINTS[setName]) console.log(`\nNext: ${SET_HINTS[setName]}`);
}

// --- post-install upgrade leg -------------------------------------------------
// Runs the set's *-setup script chain headlessly when the project already has
// the module installed. Same scripts the setup skill invokes — the bin just
// removes the agent wrapper. Fresh installs (no prior config) skip straight to
// the skill hint; prompting there actually earns its keep.

function which(cmd) {
  const exts = process.platform === 'win32' ? ['.exe', '.cmd', '.bat', ''] : [''];
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    for (const ext of exts) {
      const p = path.join(dir, cmd + ext);
      try {
        fs.accessSync(p, fs.constants.X_OK);
        return p;
      } catch {}
    }
  }
  return null;
}

function scriptRunner() {
  // Prefer uv (PEP 723 deps resolve themselves); fall back to a bare python
  // for projects that only have that — dep-free scripts still work, and the
  // yaml-dependent ones fail loudly rather than being silently skipped.
  if (which('uv'))
    return (script, args) => spawnSync('uv', ['run', script, ...args], { encoding: 'utf8' });
  for (const py of ['python3', 'python', 'py']) {
    if (which(py))
      return (script, args) => spawnSync(py, [script, ...args], { encoding: 'utf8' });
  }
  return null;
}

function moduleYamlField(yamlPath, field) {
  try {
    const m = fs
      .readFileSync(yamlPath, 'utf8')
      .match(new RegExp(`^${field}:\\s*(\\S+)`, 'm'));
    return m ? m[1] : '';
  } catch {
    return '';
  }
}

function runPostInstall(setName, root, args) {
  const hint = SET_HINTS[setName];
  const desc = POST_INSTALL[setName];
  const next = () => hint && console.log(`\nNext: ${hint}`);
  if (!desc || args.noSetup) return next();

  const skillDir = path.join(root, '.agents', 'skills', desc.setupSkill);
  const scriptsDir = path.join(skillDir, 'scripts');
  const moduleYaml = path.join(skillDir, 'assets', 'module.yaml');
  if (!fs.existsSync(moduleYaml) || !fs.existsSync(scriptsDir)) return next();

  const run = scriptRunner();
  if (!run) {
    console.log('setup: skipped — no uv/python on PATH. The skill files are installed; configure via:');
    return next();
  }

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), `skills-${setName}-`));
  const step = (name, argv, outFile) => {
    const r = run(argv[0], argv.slice(1));
    if (r.error || r.status !== 0) {
      const tail = String(r.stderr || r.stdout || r.error || '')
        .trim()
        .split('\n')
        .slice(-4)
        .join('\n');
      console.log(`setup: ${name} failed — skills are installed; fix and invoke the setup skill${tail ? `\n${tail}` : ''}`);
      return null;
    }
    const text =
      outFile && fs.existsSync(outFile)
        ? fs.readFileSync(outFile, 'utf8')
        : r.stdout || '';
    try {
      return JSON.parse(text);
    } catch {
      return {};
    }
  };

  const script = (f) => path.join(scriptsDir, f);
  const detectPath = path.join(tmp, 'detect.json');
  const detect = step('detect', [script('detect.py'), '--project-root', root, '-o', detectPath], detectPath);
  if (!detect) return;

  if (detect.mode !== 'upgrade') return next(); // fresh install — route to the skill

  console.log('\npost-install: prior install detected — running upgrade leg');

  const answersPath = path.join(tmp, 'answers.json');
  const answers = step(
    'propose-config',
    [script('propose-config.py'), '--detect', detectPath, '--module-yaml', moduleYaml, '-o', answersPath],
    answersPath
  );
  if (!answers) return;
  const code = moduleYamlField(moduleYaml, 'code') || setName;

  // --answers/--detect/--module-yaml/--report carry the values — the scripts
  // read their own artifacts instead of this file re-transcribing JSON fields
  const scaffold = step('scaffold', [
    script('scaffold.py'), '--project-root', root,
    '--answers', answersPath,
    '--module-yaml', moduleYaml,
    '--report', `${answersPath}.report.json`,
    '--mode', 'upgrade',
  ]);
  if (!scaffold) return;
  console.log(`setup    orchestration: ${scaffold.created?.length || 0} created, ${scaffold.existing?.length || 0} existing`);

  const config = step('merge-config', [
    script('merge-config.py'),
    '--config-path', path.join(root, '_bmad', 'config.yaml'),
    '--user-config-path', path.join(root, '_bmad', 'config.user.yaml'),
    '--module-yaml', moduleYaml,
    '--answers', answersPath,
    '--legacy-dir', path.join(root, '_bmad'),
  ]);
  if (!config) return;
  console.log(`setup    config merged (${code}: ${(config.module_keys || []).length} keys)`);

  const helpCsv = path.join(skillDir, 'assets', 'module-help.csv');
  if (fs.existsSync(helpCsv)) {
    const help = step('merge-help-csv', [
      script('merge-help-csv.py'),
      '--target', path.join(root, '_bmad', 'module-help.csv'),
      '--source', helpCsv,
      '--legacy-dir', path.join(root, '_bmad'),
      '--module-code', code,
      '--detect', detectPath,
    ]);
    if (!help) return;
    console.log('setup    help csv merged');
  }

  if (detect.prerequisites?.git_repo) {
    const ensured = step('ensure-lane', [
      script('ensure-lane.py'), '--project-root', root, '--answers', answersPath,
    ]);
    if (!ensured) return;
    console.log(`setup    lane: ${ensured.status}${ensured.reason ? ` (${ensured.reason})` : ''}`);
  } else {
    console.log('setup    lane: skipped (no git repo)');
  }

  // Surface config keys that got defaults — an agent upgrade would have asked;
  // the bin can't, so it reports instead.
  try {
    const report = JSON.parse(fs.readFileSync(answersPath + '.report.json', 'utf8'));
    const prior = detect.prior_cdo_config || {};
    const defaulted = (report.proposed || [])
      .filter((p) => p.source === 'default' && !p.key.startsWith('core.') && p.key !== 'backlog_map' && !(p.key in prior))
      .map((p) => p.key);
    if (defaulted.length)
      console.log(`setup    new config keys defaulted: ${defaulted.join(', ')} — change via the ${desc.setupSkill} skill (--set key=value)`);
  } catch {}
}

function run(setName) {
  const pkgRoot = path.resolve(__dirname, '..');
  const args = parseArgs(process.argv.slice(2));
  if (args.version) {
    console.log(require(path.join(pkgRoot, 'package.json')).version);
    return;
  }
  if (args.list) {
    const skills = listSkills(path.join(pkgRoot, 'sets', setName));
    console.log(`${setName} ships ${skills.length} skills:`);
    for (const s of skills) console.log(`  ${s}`);
    return;
  }
  install(setName, pkgRoot, args);
}

module.exports = { run };
