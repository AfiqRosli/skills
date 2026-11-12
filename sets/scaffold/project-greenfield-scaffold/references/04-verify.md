# Stage 4 — Verify

**Prerequisite:** dependencies installed, `.nuxt` prepared.

The scaffold is only done when it's green. Run the verify orchestrator — it runs each check the rendered package.json actually defines, and emits compact JSON (pass/fail + a short tail on failure) instead of flooding context with full build logs:

```bash
python3 ./scripts/verify.py <target>
```

It discovers checks from `<target>/package.json` scripts (type-check → lint → test:run → build), so disabled modules are skipped automatically. If Python can't run, run the same commands yourself and report pass/fail per check. If `build` is too slow for the loop, `bun run dev` + hit `/` and `/api/hello` is an acceptable smoke substitute — say which you ran.

Fix failures against the spine (`./references/spine-manifest.md`), not around them. Common drift repairs: renamed module options, import-path changes in the pinned majors, stricter lint rules in newer `@stylistic`/eslint majors.

Then deliver the health report:

- Module set rendered (enabled / disabled / auto-disabled)
- Verify results per command
- **Operator checklist** — what only a human can finish: real `DATABASE_URL`, `BETTER_AUTH_SECRET`, OAuth keys, Polar product IDs, `RESEND_API_KEY`, `SENTRY_DSN`, `REDIS_URL`, favicon files in `public/`, Netlify site link (`netlify link`)
- Point at `docs/getting-started.md` and `.devin/rules/code-style-guide.md` as the onboarding reads

Persist the health report — the scaffold script already wrote `<target>/.scaffold-report.json` at render time; append the verify results there (or include them in it) so a later session or pipeline step can resume from state instead of archaeology.

**Workflow complete** — this is the terminal stage; the report is the deliverable.
