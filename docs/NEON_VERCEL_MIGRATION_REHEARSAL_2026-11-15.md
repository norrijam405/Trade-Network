# Trade Network — Neon + Vercel Migration Rehearsal

Date: 2026-11-15 / 2026-11-16 UTC

## Goal
Create a Render-independent pilot path without changing production or merging main.

## Current architecture recommendation
- Database target: **Neon Postgres**
- Web/API target: **Vercel FastAPI preview**
- Alternate host lane: Cloudflare Python Workers, held as fallback because the current persistence adapter uses CPython + `psycopg`, which is a lower-friction fit on Vercel.

## Neon target
Project: `Trade Network Pilot`
Project ID: `snowy-scene-84184020`
Plan: `free_v3`
Region: `aws-us-east-1`
Postgres: 18
Project storage limit: 1 GiB
Default compute: 0.25 CU, scale-to-zero
History retention observed: 21600 seconds

Default branch:
- `br-muddy-credit-bc5ll36w`
- database: `trade_network`
- owner: `trade_network_owner`

Before rehearsal, main contained:
- `trade_network_pilot_state`
- `trade_network_pilot_events`

Both core tables matched the Render schema and were empty. Main was not used for rehearsal writes.

## Isolated Neon rehearsal branch
Branch: `r3-migration-rehearsal-2026-11-15`
Branch ID: `br-snowy-cherry-bcplj5ld`

On the isolated branch:
1. created `trade_network_pilot_durability`,
2. wrote fictional state marker `FICTIONAL_NEON_R3`,
3. wrote one fictional event,
4. read snapshot/event/durability values back,
5. repeated a separate durability write/read.

DB-level readback:
- migration probe: `FICTIONAL_NEON_R3`
- event count: `1`
- durability counter: `1 -> 2`

## Actual application runtime portability proof
Trade Network runtime SHA:
`bad4ab74be36dc2e63c0347c9ad0dc764452a1fd`

GitHub Actions:
- workflow: `Trade Network R3 House Gates`
- run: `43798936562`
- result: **SUCCESS**

The Neon rehearsal connection was injected into the existing isolated Render R3 service as secret environment variable `NEON_STANDBY_URL`; the connection string was not printed or committed.

### First attempt — blocked and diagnosed
The first standby launch logged:
- `HOUSE_SELFTEST PASS checks=9`
- `NEON_STANDBY FAIL ProgrammingError`
- `PERSISTENCE_ROUNDTRIP PASS`
- primary durability continued advancing.

Cause: the Neon connector returned a formatted connection-details block and the initial environment binding mistakenly used the whole formatted block rather than extracting only the actual `postgresql://...` URL.

This was a migration-harness bug, not a Neon schema or network failure.

### Corrected exact-SHA replay
The actual PostgreSQL URL was extracted programmatically without exposing it, and the same exact runtime SHA was redeployed.

Render deploy:
`dep-dbt7kau1egvs73fldip0`

Result:
- **LIVE**
- `HOUSE_SELFTEST PASS checks=9`
- **`NEON_STANDBY PASS restart_count=3`**
- `PERSISTENCE_ROUNDTRIP PASS`
- primary Render `PERSISTENCE_DURABILITY restart_count=12`
- repeated `/health` 200
- public `GET /` 200

This proves the real FastAPI + psycopg application runtime can connect to and write/read the isolated Neon Postgres target while the existing primary Render persistence path remains healthy.

**Database portability to Neon = VERIFIED for the isolated fictional pilot path.**

This does not yet authorize switching the primary database.

## Standby privacy/authority boundary
An Admin-only `/api/admin/standby` status exists.
Regression tests require:
- non-Admin denial,
- Admin read allowed,
- no connection URL or password returned.

## Vercel discovery and blocker
Connected Vercel team:
- `norrijam405-2107's projects`
- plan: Hobby/free

Attempts to create `trade-network-preview`:
1. Git-linked project creation -> HTTP 403 forbidden.
2. Direct project creation -> HTTP 403 forbidden.
3. documented CLI fallback unavailable in the execution environment.

Per Vercel error guidance, the forbidden create action was not repeatedly retried.

**Vercel web-host migration = BLOCKED ON PROJECT-CREATE AUTHORITY, not application code.**

## Repo preparation
Added:
- `pyproject.toml`
- `.python-version`
- `scripts/verify_postgres_target.py`
- this rehearsal record

## Current acceptance gate for Render removal
1. Obtain/create a preview web-host project with appropriate authority.
2. Bind only the Neon rehearsal/standby target.
3. Deploy exact reviewed Trade Network SHA.
4. Require homepage + health 200.
5. Require House self-test PASS.
6. Require persistence roundtrip PASS.
7. Require Neon durability to advance across redeploy.
8. Run wrong-role, expired/revoked-session, employer-isolation and duplicate/replay gates.
9. Keep current Render R3 as rollback.
10. Only after exact-host proof should Render removal be considered.

## Hard boundaries
- No paid infrastructure.
- No production merge.
- No real user/customer/employer data.
- No credential output in GitHub, logs or docs.
- No weakening DB network/security controls for convenience.
- Cost Layer 2.0 remains separate from worker truth, credential status, ranking, disputes and verification.
