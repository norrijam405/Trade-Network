# Trade Network R3 — Verified Plumbing Receipt

Date: 2026-11-15

## Exact source
- Repository: `norrijam405/Trade-Network`
- Branch: `launch/r2-hosted-preview`
- Syntax-clean deployed SHA: `d5950579a46cf4d0c8fa1c1c002eec20cb8843b1`
- Draft PR: #2

## CI
GitHub Actions workflow: **Trade Network R3 House Gates**
- Exact-head run: `43776683050`
- Result: **COMPLETED / SUCCESS**
- Gates cover invalid sessions, wrong-role access, duplicate intro suppression, second-employer isolation, duplicate meeting suppression, duplicate customer-request suppression, blank-message rejection, and Admin decision state remaining `UNKNOWN`.

## Hosted R3
- Render service: `trade-network-r3-persistent-preview-c4pa`
- Service ID: `srv-dbsstvoae00c739055g0`
- Exact-head deploy: `dep-dbt492jbc2fs73d2umr0`
- URL: https://trade-network-r3-persistent-preview-c4pa.onrender.com
- Status: **LIVE**
- Public GET /: 200
- Health checks: repeated 200

## Startup verification receipts
At exact deployed SHA:
- `HOUSE_SELFTEST PASS checks=7`
- `PERSISTENCE_ROUNDTRIP PASS`
- `PERSISTENCE_DURABILITY restart_count=4`

Earlier same-SHA/redeploy receipts advanced the database-backed durability sentinel from restart_count 1 -> 2. Subsequent exact-head deployments advanced to 3 -> 4. This proves the isolated Postgres durability marker survives real process replacement/redeploy.

## What is now verified
- Web service can connect to the isolated Render Postgres database without exposing the credential.
- Application state snapshot can be written to Postgres, cleared in memory, restored from Postgres, detected, and safely returned to the original snapshot.
- Database-backed durability metadata survives multiple process replacements.
- Current source-level authorization and duplicate/isolation rules pass GitHub CI and the deployed startup self-test.

## Still NOT verified / not production
- Real-user multi-tenant security or penetration testing.
- Durable idempotency under concurrent multi-instance writes.
- Production authentication, MFA/passkeys, account recovery hardening.
- Backup restore from an independent backup artifact.
- Retention/deletion implementation.
- Real employers/jobs/customer data.
- Cost Layer 2.0 enforcement.
- Regulatory credential/hour acceptance.
- Production readiness or production merge.

No real customer data, paid infrastructure, production merge, permission mutation or credential exposure was used for these receipts.
