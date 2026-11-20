# Auth Infra Foundation — `dash()` + `sentinel`/`sentinelClient`

Distilled from the source `auth.ts` (root) and `lib/auth-client.ts`. This is the
reference for adding the `@better-auth/infra` plugin pair when a scaffolded
project wants Better Auth Dash (admin/audit) and Sentinel (abuse protection).
The current template renders neither — this doc is the foundation for adding
an `infra`/`sentinel` module flag or porting the pattern by hand.

**Reference implementation** — the source repo (PRTO) carries the live version
this doc was distilled from: `auth.ts` (server plugin array), `lib/auth-client.ts`
(`sentinelClient`), `server/lib/sentinel-bypass.ts` (the `withAdminBypass`
spec — its docblock is authoritative), `@better-auth/infra` `^0.4.0` in
`package.json`. If you have that checkout, read `sentinel-bypass.ts` before
porting; if not, this doc alone is sufficient — every invariant a port must
keep is listed below.

## The shape

Two plugin halves, server and client — both required or the feature is broken:

```ts
// auth.ts (server)
import { dash, sentinel } from "@better-auth/infra";

plugins: [
  dash(),                                            // 1. always on, all defaults
  ...(process.env.SENTINEL_ENABLED === "true"         // 2. opt-in via env
    ? [withAdminBypass(sentinel({
        apiKey: process.env.BETTER_AUTH_API_KEY,
        security: { /* per-check config */ },
      }))]
    : []),
  organization({ /* ... */ }),                       // 3. domain plugins after infra
  polar({ /* ... */ }),
]
```

```ts
// lib/auth-client.ts (browser)
import { sentinelClient } from "@better-auth/infra/client";

plugins: [
  organizationClient(),
  polarClient(),
  sentinelClient({
    autoSolveChallenge: true,
    identifyUrl: process.env.BETTER_AUTH_IDENTIFY_URL,
  }),
]
```

`dashClient` also exists in `@better-auth/infra/client` but the source project
does not use it — Sentinel is the only client-side infra plugin wired.

## What each piece does

| Piece | Package | Role |
| ----- | ------- | ---- |
| `dash()` | `@better-auth/infra` | Better Auth Dash control plane: `/dash/*` admin endpoints, audit logs, user/org management, optional `activityTracking`. Registers `databaseHooks` (user create/update/delete, session create) for event projection. |
| `sentinel()` | `@better-auth/infra` | Abuse protection: visitor identification, PoW challenges, and nine security checks. Blocks at **three layers** (below). |
| `sentinelClient()` | `@better-auth/infra/client` | `{ id: "sentinel", fetchPlugins }` — fetch middleware that attaches visitor identity and auto-solves PoW challenges. |
| `withAdminBypass()` | `server/lib/sentinel-bypass.ts` | Wraps the `sentinel()` plugin object so `NUXT_ADMIN_EMAILS` skip all three blocking layers, with an audit log line per bypass. |

## Sentinel's three blocking layers — the reason `withAdminBypass` exists

`sentinel()` can reject a request at any of three points; bypassing one is not
enough:

1. **`rateLimit.customRules`** (set in plugin `init`) — `applyCoordination` →
   `resolveAdmission` (velocity, freeTrialAbuse) runs *before* any before-hook.
2. **`hooks.before`** — `runSecurityChecks` → `applyAdmission` throws
   `APIError("FORBIDDEN")` for credentialStuffing, compromisedPassword,
   emailValidation, impossibleTravel.
3. **`databaseHooks.user.create.before`** (set in `init`) — throws when
   `!visitorId` ("Account creation is not allowed without device
   identification") or when `reserveFreeTrialSignup` detects abuse.

`withAdminBypass` wraps `init`'s returned `customRules` + `databaseHooks` and
re-maps every `hooks.before` matcher (returns `false` for admin emails after
preserving the original matcher's own skip logic). The allowlist parses
`NUXT_ADMIN_EMAILS` once at module load; every bypass writes a `logger.info`
audit line.

## Invariants — decisions a re-implementation must not quietly change

1. **Client and server Sentinel are a pair.** `sentinel()` on the server issues
   PoW challenges and requires a `visitorId` at user-create; only
   `sentinelClient({ autoSolveChallenge: true })` solves challenges and supplies
   identity. Server-only = users die on the first challenge. Client-only = no
   checks run.
2. **Sentinel is opt-in via `SENTINEL_ENABLED=true`**, spread-conditional — the
   plugin object is never constructed when off. Rationale: velocity /
   freeTrialAbuse limits trip on repeated test signups from one IP and would
   block preview/staging smoke tests. Production sets the flag.
3. **Infra plugins lead the plugins array** (`dash` → `sentinel` → domain
   plugins). Their `init` contributes `rateLimit.customRules` and
   `databaseHooks` that other plugins' flows depend on.
4. **Fail closed everywhere.** Empty `NUXT_ADMIN_EMAILS` → nobody bypasses.
   Unparseable request body in `getRequestEmail` → Sentinel runs normally.
   A bypass helper must never silently widen access.
5. **`emailNormalization.enabled: false` in security config when the app has
   its own `normalizeEmail`.** Sentinel's version maps `googlemail.com` →
   `gmail.com`; the app's helper doesn't. Enabling both splits one user's
   identity across two canonical forms. Pick exactly one normalizer.
6. **Challenge vs block is per-check, deliberate:** `block` —
   compromisedPassword, emailValidation, freeTrialAbuse, suspiciousIpBlocking;
   `challenge` — impossibleTravel (VPN false positives), botBlocking (headless
   test browsers), velocity; `credentialStuffing` uses both (`challenge: 3`,
   `block: 5`). Never blanket-`block` — VPNs and CI will lock out real users.
7. **`advanced.ipAddress.ipAddressHeaders` must list the host's real-client-IP
   header** (`["x-nf-client-connection-ip", "x-forwarded-for"]` on Netlify).
   Velocity and impossible-travel key on the request IP — behind a proxy
   without this, every user shares the edge IP and rate limits collapse.
8. **`challengeDifficulty` stays ≤ 18** (default) without load-testing —
   it's a client-side PoW cost paid per challenge.
9. **Every bypass is audited.** Admin bypass paths `logger.info` the event —
   a compromised admin account must leave a trail.
10. **`BETTER_AUTH_API_KEY` is the shared connection secret** — `apiUrl`
    (`https://dash.better-auth.com`), `kvUrl` (`https://kv.better-auth.com`),
    and `identifyUrl` all default to Better Auth's hosted services; only
    self-hosted deployments override them.

## Env var contract

| Var | Consumed by | Required |
| --- | ----------- | -------- |
| `BETTER_AUTH_API_KEY` | `sentinel({ apiKey })` (dash uses it by default too) | when dash/sentinel on |
| `SENTINEL_ENABLED` | plugins-array gate | only `= "true"` enables |
| `BETTER_AUTH_IDENTIFY_URL` | `sentinelClient({ identifyUrl })` | optional (hosted default) |
| `NUXT_ADMIN_EMAILS` | `isAdminEmail` in `server/lib/sentinel-bypass.ts` (comma-separated) | optional; empty = no bypass |

`BETTER_AUTH_API_KEY` is server-side only — never in `runtimeConfig.public`.
`NUXT_ADMIN_EMAILS` is already shared with `isAdmin`/`runtimeConfig.adminEmails`
in the source project; reuse that allowlist rather than inventing a second one.
Hosted `apiUrl`/`kvUrl`/`identifyUrl` endpoints are the default — self-hosting
overrides are a downstream decision, not a scaffold-time one.

## Scaffold porting notes

- **Candidate flag:** `sentinel` (or fold into `auth` with a `SENTINEL_ENABLED`
  env gate only). Requires `auth`; `sentinel-bypass.ts` lives under
  `server/lib/` so `excluded_paths` + `// @flag sentinel` blocks in `auth.ts`
  and `lib/auth-client.ts` cover removal. Dep: `@better-auth/infra` only.
- **`dash()` needs no flag-block** — it's one line + one import. Either always
  render it or gate it with the same `infra`/`sentinel` flag; don't split them.
- **`withAdminBypass` ships as its own file** (`server/lib/sentinel-bypass.ts`)
  — it wraps the plugin object structurally (init/hooks/matchers), so it must
  live outside `auth.ts` to keep the config readable. Port it verbatim; its
  docblock is the spec.
- **Minimal viable config** for a greenfield that wants Sentinel: keep
  `credentialStuffing`, `compromisedPassword`, `emailValidation`,
  `emailNormalization: false` (if a custom normalizer exists), `velocity`
  (challenge). Leave `freeTrialAbuse` off unless the product has a free trial —
  it double-counts signups per visitor.
- **Don't port** `staleUsers`/`geoBlocking` (off in source — revisit at scale),
  `managedDirectorySync`, or `dashClient`.
- **Verify-stage check:** with `SENTINEL_ENABLED` unset, boot must succeed with
  no `BETTER_AUTH_API_KEY` — the conditional spread guarantees no construction.
  Set the flag only after `BETTER_AUTH_API_KEY` exists in `.env`.
