# Trade Network — Neon + Vercel Migration Rehearsal

Date: 2026-11-15

## Goal
Create a Render-independent pilot path without changing production or merging main.

## Current recommendation
- Database target: Neon Postgres
- Web/API target: Vercel FastAPI preview
- Alternate host lane: Cloudflare Python Workers, held as fallback because the current Postgres adapter uses psycopg and Vercel offers lower-friction CPython compatibility.

## Neon target
Project: `Trade Network Pilot`
Project ID: `snowy-scene-84184020`
Plan: `free_v3`
Region: `aws-us-east-1`
Postgres: 18
Project storage limit: 1 GiB
Default compute: 0.25 CU with scale-to-zero behavior

Default branch:
- `br-muddy-credit-bc5ll36w`
- database: `trade_network`
- owner: `trade_network_owner`

Existing main-branch tables before rehearsal:
- `trade_network_pilot_state`
- `trade_network_pilot_events`

Both were empty before the isolated rehearsal.

## Isolated rehearsal branch
Branch: `r3-migration-rehearsal-2026-11-15`
Branch ID: `br-snowy-cherry-bcplj5ld`

On the isolated branch only:
1. created `trade_network_pilot_durability`,
2. wrote fictional snapshot marker `FICTIONAL_NEON_R3`,
3. wrote one fictional event,
4. read the snapshot/event/durability values back,
5. performed a second read and advanced the durability counter from 1 to 2.

Observed readback:
- migration probe: `FICTIONAL_NEON_R3`
- event count: `1`
- durability restart counter: `1 -> 2`

This proves schema compatibility and durable state retention in Neon for the current pilot model. It does NOT yet prove the deployed FastAPI app has run against Neon.

## Vercel discovery
Connected Vercel team:
- `norrijam405-2107's projects`
- plan: Hobby/free

The connected Vercel app can inspect the team, but project creation returned HTTP 403 `forbidden`. The same forbidden create action was not retried unchanged.

No production Vercel deployment exists yet.

## Repo preparation
Added:
- `pyproject.toml` with FastAPI/Pydantic/psycopg dependencies and Vercel entrypoint `preview_runner:app`
- `.python-version` pinned to Python 3.12
- `scripts/verify_postgres_target.py` for privacy-safe Postgres target verification

Render remains the current verified hosted preview until a separate Vercel/alternate-host preview passes House gates.

## Acceptance gate for Render removal
1. Create/obtain preview-host project authority.
2. Bind only the isolated Neon rehearsal branch.
3. Deploy exact reviewed Trade Network SHA.
4. Require homepage + health 200.
5. Require House self-test PASS.
6. Require persistence roundtrip PASS.
7. Require database durability counter to advance across a new deployment.
8. Run wrong-role, expired/revoked-session, employer-isolation and duplicate/replay gates.
9. Keep Render rollback available.
10. Only after all pass, consider replacing the current Render preview.

## Hard boundaries
- No paid infrastructure.
- No production merge.
- No real user/customer/employer data.
- No credential output in GitHub, logs or docs.
- No weakening database network controls merely for convenience.
- Cost Layer 2.0 remains separate from worker truth, credential status, ranking, disputes and verification.
