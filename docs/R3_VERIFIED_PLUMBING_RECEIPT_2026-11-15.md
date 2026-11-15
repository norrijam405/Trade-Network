# Trade Network R3 — Verified Plumbing Receipt

Date: 2026-11-15

## Exact source and deployment
- Repository: `norrijam405/Trade-Network`
- Branch: `launch/r2-hosted-preview`
- Current verified runtime source SHA: `371d1aa126769d4eb2bb2df66333679d7c1c1e6f`
- Draft PR: #2
- Render service: `trade-network-r3-persistent-preview-c4pa`
- Service ID: `srv-dbsstvoae00c739055g0`
- Exact deploy: `dep-dbt4b7e7bikc73d0nd30`
- URL: https://trade-network-r3-persistent-preview-c4pa.onrender.com
- Render status: **LIVE**
- Public GET /: **200**
- Repeated /health checks: **200**

## Exact-head CI
GitHub Actions workflow: **Trade Network R3 House Gates**
- Exact-head run for persistence telemetry gate: `43777045898`
- Result: **COMPLETED / SUCCESS**
- Earlier exact-head session-hardening run: `43776859138` **SUCCESS**
- Syntax-clean runtime run: `43776683050` **SUCCESS**

Current gates cover:
- invalid session fails closed,
- wrong role cannot access Worker data,
- duplicate intro suppression,
- second fictional employer isolation,
- duplicate meeting suppression,
- duplicate customer-request suppression,
- blank-message rejection,
- Admin decision state remains `UNKNOWN`,
- expired session rejection/removal,
- logout/session revocation,
- anonymous persistence telemetry minimization,
- Customer denied detailed persistence telemetry,
- Admin permitted detailed persistence telemetry.

## Deployed startup receipts
At current exact deployed SHA:
- `HOUSE_SELFTEST PASS checks=9`
- `PERSISTENCE_ROUNDTRIP PASS`
- `PERSISTENCE_DURABILITY restart_count=6`

Earlier redeploys advanced the same database-backed sentinel through restart counts 1 -> 2 -> 3 -> 4 -> 5 -> 6 across real process replacements.

## Verified plumbing claims
The following are now evidence-backed for the isolated fictional R3 preview:
1. Web service connects to isolated Render Postgres without exposing the credential.
2. Application state snapshot can be written to Postgres, cleared from memory, restored from Postgres and then restored to its original snapshot.
3. Database-backed durability metadata survives repeated service replacements/redeploys.
4. Current authorization, isolation and duplicate guards pass GitHub CI and startup self-test.
5. Demo sessions have a two-hour TTL and explicit logout revocation.
6. Anonymous persistence status exposes coarse readiness only; detailed operational persistence metadata requires the Admin role.
7. Historical invalid Python terminal marker was removed; current source is syntactically valid without runtime repair.

## Infrastructure deadline
Current free Render Postgres database:
- ID: `dpg-dbssg2t6e07s73aop74g-a`
- expires: **2026-12-15**
- recommended permanent-database migration target: **on or before 2026-12-08**

The database external allowlist remains empty. It was **not** weakened for inspection.

## Still NOT verified / not production
- Real-user multi-tenant penetration/security testing.
- Durable idempotency under concurrent multi-instance writes.
- Independent backup artifact -> restore drill.
- Retention/deletion implementation.
- Production authentication/MFA/passkeys/recovery.
- Real employer/job/customer data.
- Real job feed/provider integrations.
- Cost Layer 2.0 enforcement in Trade Network.
- Credential/licensing/hour authority.
- Production readiness or production merge.

No real customer data, paid infrastructure, production merge, permission mutation, external database allowlist change, or credential exposure was used for these receipts.
