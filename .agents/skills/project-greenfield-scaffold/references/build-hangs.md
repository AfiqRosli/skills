# Build Exit-Hang & Push-Stall — enforcement rules and diagnosis

Field lesson: a module-scope `setInterval` (never `.unref()`'d) in a Nitro
server module was evaluated inside `nuxi build` the moment a route opted into
prerendering — `nuxt-elysia`'s generated plugin eagerly imports every router
on each Nitro boot, and prerender boots Nitro in-process. The pending timer
pinned the event loop: builds printed "complete" but never exited → zombie
`nuxi` processes accumulated → `.nuxt`/`.output` file-lock contention → pushes
stalled 50+ min in the pre-push hook → Netlify builds hit the 18-min wall
post-completion. One `.unref()` was the fix; the rules below are the systemic
one.

## Enforcement rules

1. **No ref'd handles at module scope.** Any top-level `setInterval`,
   `setTimeout`, socket, pool, or SDK client in server modules must be
   `.unref()`'d, lazy behind a function call (the spine's `getRedis()`/lazy-`db`
   pattern), or explicitly closed on shutdown. Module-eval code runs inside
   every Nitro boot — dev server, tests, prerender, and `nuxi build`.
   When adapting, grep server code for `setInterval|setTimeout|new Redis|
   new Pool|connect(` at top level.

2. **`prerender: true` = your app boots inside the build.** Any route opting
   into build-time prerendering evaluates the full server bundle inside
   `nuxi build` — same process, same event loop. The spine ships `swr`
   routeRules (CDN cache headers — no in-build boot); if adaptation adds
   `prerender`, "successful build" means the process *exits*, not just prints
   complete. `verify.py`'s check timeout enforces this.

3. **Every build/test invocation has a guaranteed exit.** `verify.py` bounds
   each check by `--check-timeout` (default 1200s) and kills the tree on
   expiry; the shipped pre-push (`scripts/pre-push-build-validation.sh`,
   invoked by `.husky/pre-push`) wraps its commands in `timeout` — warn-and-run
   unbounded when `timeout` is absent, as on Git Bash.
   Never run two `nuxi` builds concurrently in one tree — `.nuxt`/`.output`
   file-lock contention turns a 10-min build into an hour. If a pipeline can
   trigger concurrent builds, guard with a lockfile or a `pgrep -f nuxi`
   check first.

4. **If a pre-push gate runs a build, use stamp-passed design — never
   range-diff.** The shipped pre-push is deliberately cheap (type-check +
   tests; the full build is CI's job). When a project does want a build gate,
   the stamp pattern preserves validation strength while making retries free:

   ```bash
   STAMP=.git/pre-push-build-stamp
   TREE_SHA=$(git rev-parse 'HEAD^{tree}')

   if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$TREE_SHA" ]; then
     echo "Build already verified for this exact tree — skipping."
   else
     timeout 1200 bash -c "$BUILD_CMD" || { echo "Build failed or timed out."; exit 1; }
     echo "$TREE_SHA" > "$STAMP"
   fi
   ```

   Still gates on any build-critical change in the pushed range; a failed or
   killed push re-pushes instantly (same tree, stamp matches); tree-hash not
   commit-sha means amended/rebased commits with identical content reuse the
   stamp; the hard timeout means even a future exit-hang fails loudly in
   ≤20 min instead of hanging forever.

## Diagnosis — marker, not duration

If a build/deploy log shows the success marker (`Build complete!`, `built in`,
`✓`) *before* the timeout kill, the bug is **process exit**, not build speed —
find the leaked handle; bundle size and plugin warnings are secondary.
Caveat: on Node ≥ 22, `process._getActiveHandles()` does not report `Timeout`
objects — instrument `setTimeout`/`setInterval` directly; don't trust the
handles API.

`verify.py` surfaces this for you: a check that hits `--check-timeout` reports
`timed_out: true` plus its output tail — a completion marker in that tail
means exit-hang, not slow build.
