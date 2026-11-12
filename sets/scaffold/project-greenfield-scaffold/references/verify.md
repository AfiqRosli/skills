# Stage 4 — Verify

**Prerequisite:** dependencies installed, `.nuxt` prepared.

The scaffold is only done when it's green. Run the verify orchestrator — it runs each check the rendered package.json actually defines, and emits compact JSON (pass/fail + a short tail on failure) instead of flooding context with full build logs:

```bash
python3 scripts/verify.py <target>
```

It discovers checks from `<target>/package.json` scripts (type-check → lint → test:run → build), so disabled modules are skipped automatically. It then runs `dev-boot`: spawns `bun run dev` on a scratch port and probes `/` and `/api/hello` for 200 (`--no-dev` to skip, `--dev-timeout` to tune). dev-boot exists because import-time crashes — a client constructed without env — pass every static check and 500 every route at request time; placeholder-env bootability is part of "green", not a nicety. Deliberately no DB-dependent probes: they legitimately 500 on the shipped placeholder `DATABASE_URL`.

If Python can't run, do the same yourself: the four static checks plus a manual `bun run dev` smoke hitting `/` and `/api/hello` — report which you ran.

Fix failures against the spine (`references/spine-manifest.md`), not around them. Common drift repairs: renamed module options, import-path changes in the pinned majors, stricter lint rules in newer `@stylistic`/eslint majors.

Then deliver the health report:

- Module set rendered (enabled / disabled / auto-disabled)
- Verify results per command
- **Operator checklist** — what only a human can finish: real `DATABASE_URL`, `BETTER_AUTH_SECRET`, OAuth keys, Polar product IDs, `RESEND_API_KEY`, `SENTRY_DSN`, `REDIS_URL`, favicon files in `public/`, Netlify site link (`netlify link`)
- Point at `docs/getting-started.md` and `.devin/rules/code-style-guide.md` as the onboarding reads

The orchestrator persists its report into `<target>/.scaffold-report.json` under a `verify` key, and `scaffold.py --status` surfaces it in `resume_hint` — a later session sees a finished verify leg instead of re-running it. Your job is only the health report above.

**Workflow complete** — this is the terminal stage; the report is the deliverable.
