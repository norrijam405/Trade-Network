# Trade Network Pilot Persistence Runbook

## Temporary infrastructure
The current R3 pilot database is a **free Render Postgres preview database**:
- Render database ID: `dpg-dbssg2t6e07s73aop74g-a`
- Database name: `trade-network-r2-pilot-db`
- Region: Ohio
- Free-tier expiration: **2026-12-15**
- Network posture: external allowlist remains empty. Do not weaken it merely for inspection.

This is pilot infrastructure, not a permanent production database.

## Migration deadline
Target permanent-data migration **before 2026-12-08** to leave a seven-day recovery margin before free-database expiration.

Do not begin a real-user pilot until:
1. a permanent database destination is chosen,
2. the schema and state export/import path are tested with fictional data,
3. tenant boundaries are independently challenged,
4. backup and restore are demonstrated,
5. retention/deletion policy is documented,
6. production authentication is separated from demo identities.

## Safe backup principle
Never expose `DATABASE_URL`, passwords, raw private worker/customer data, or secrets in GitHub issues/logs.

For the current fictional preview:
1. quiesce writes or use a consistent transaction/snapshot,
2. export schema + data through provider-approved tooling,
3. hash the backup artifact,
4. restore into an isolated destination,
5. compare counts and a privacy-safe state hash,
6. run the House gates and critical journey,
7. only then move the application connection,
8. keep rollback available until readback succeeds.

## Rollback
If a migrated preview fails:
- leave the old R3 database untouched while it remains available,
- restore the previous service/database binding,
- confirm `/health`,
- verify the persistence status and critical journey,
- record the failed migration as evidence; do not silently retry destructive steps.

## Current evidence
See `R3_VERIFIED_PLUMBING_RECEIPT_2026-11-15.md`.

## Hard boundaries
- No production merge without separate founder release approval.
- No paid plan or infrastructure without explicit approval.
- No real customer data until privacy/auth/retention gates pass.
- Cost Layer 2.0 never changes worker truth, credential status, hiring verification, or dispute outcomes.
