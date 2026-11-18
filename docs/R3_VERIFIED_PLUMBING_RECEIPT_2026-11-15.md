# Trade Network R3 — Verified Plumbing Receipt

Date: 2026-11-15 / 2026-11-16 UTC

## Current exact runtime
- Repository: `norrijam405/Trade-Network`
- Branch: `launch/r2-hosted-preview`
- Draft PR: #2
- Runtime SHA: `bad4ab74be36dc2e63c0347c9ad0dc764452a1fd`
- Render service: `srv-dbsstvoae00c739055g0`
- Current exact deploy: `dep-dbt7kau1egvs73fldip0`
- URL: https://trade-network-r3-persistent-preview-c4pa.onrender.com
- Status: **LIVE**

## Exact-head CI
GitHub Actions:
- workflow: `Trade Network R3 House Gates`
- run `43798936562`
- conclusion: **SUCCESS**

Current regression gates include session failure/expiry/revocation, RBAC, employer isolation, duplicate suppression, blank-message rejection, Admin UNKNOWN truth state, minimized public persistence telemetry and Admin-only detailed persistence/standby status.

## Current deployed receipts
- `HOUSE_SELFTEST PASS checks=9`
- **`NEON_STANDBY PASS restart_count=3`**
- `PERSISTENCE_ROUNDTRIP PASS`
- **primary Render `PERSISTENCE_DURABILITY restart_count=12`**
- repeated `/health` 200
- public `GET /` 200

## Database portability
An isolated Neon project/branch is now independently exercised by the real FastAPI + psycopg runtime:
- Neon project: `Trade Network Pilot`
- project ID: `snowy-scene-84184020`
- rehearsal branch: `br-snowy-cherry-bcplj5ld`
- database: `trade_network`

Neon main was read-only during rehearsal. The rehearsal branch contains fictional migration state only.

The app verified the fictional migration marker and advanced Neon durability to 3 while primary Render Postgres remained healthy.

**Current evidence supports: DATABASE PORTABILITY TO NEON = VERIFIED for isolated fictional pilot use.**

It does **not** support production migration or web-host independence yet.

## Current web-host blocker
Vercel Hobby/free is the preferred first Render-free FastAPI target because current Vercel Python/FastAPI hosting uses standard CPython and minimizes application rewrite.

However the connected Vercel account currently returns HTTP 403 for project creation. Full Render-free web hosting is therefore **BLOCKED ON EXTERNAL VERCEL PROJECT-CREATE AUTHORITY**.

Cloudflare remains an alternate lane, but moving the current psycopg persistence path there would require more adapter/runtime work.

## Temporary Render database deadline
Current primary free Render DB:
`dpg-dbssg2t6e07s73aop74g-a`

Expiration: **2026-12-15**
Migration target: **on or before 2026-12-08**

Because Neon portability is now proven, the database-expiry risk has been materially reduced; an exact primary cutover and rollback rehearsal are still required before switching.

## Still NOT verified / not production
- real-user multi-tenant penetration testing,
- concurrent/multi-instance atomic idempotency,
- independent backup artifact -> restore drill,
- retention/deletion implementation,
- production auth/MFA/passkeys/recovery,
- real employer/job/customer data,
- real provider/job feeds,
- Render-free web deployment,
- Cost Layer 2.0 enforcement,
- credential/licensing/hour authority,
- production readiness or production merge.

No real customer data, paid infrastructure, production merge, credential disclosure or consequential employment automation was used.
