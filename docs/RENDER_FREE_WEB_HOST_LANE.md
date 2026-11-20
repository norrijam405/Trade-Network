# Render-Free Web Host Lane

## Canonical runtime
Container entrypoint:
`uvicorn preview_runner:app --host 0.0.0.0 --port $PORT`

The container uses the same:
- `preview_runner.py`
- `hosted_preview.py`
- `requirements-preview.txt`
- Python 3.12

as the verified R3 hosted preview.

## Preferred order
1. Vercel FastAPI + Neon — lowest rewrite, currently blocked by Vercel project-create authority.
2. Koyeb free web service + Neon — strongest current no-cost container/Git fallback.
3. Google Cloud Run + Neon — technically strong but billing-account based.
4. Cloudflare Python Workers — viable but requires more persistence/runtime adaptation for current psycopg path.

## Koyeb preview configuration
Use a Web Service, not Worker Service.

Recommended pilot settings:
- Source: GitHub `norrijam405/Trade-Network`
- Branch: `launch/r2-hosted-preview`
- Builder: Dockerfile
- Instance: Free
- Region: Washington, D.C. if available
- Port: platform-provided `PORT`
- Health endpoint: `/health`
- Secret: `DATABASE_URL` -> isolated Neon preview/rehearsal database URL
- Do not set real-user secrets or production data.

Acceptance:
1. container build succeeds,
2. homepage 200,
3. /health 200,
4. House startup self-test PASS,
5. persistence roundtrip PASS,
6. Neon durability advances across a redeploy/restart,
7. RBAC/session/isolation regression passes,
8. exact SHA recorded,
9. Render R3 retained as rollback until proof is complete.

## Important
The former Dockerfile built a stale R1 ZIP/frontend tree. It was replaced because it was not source-equivalent to current R3.
