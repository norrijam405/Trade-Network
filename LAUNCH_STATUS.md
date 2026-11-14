# Trade Network Launch Status

Date: 2026-11-13
Branch: `launch/r0-2026-11-13`
State: WINDOWS USER-LIVE RETEST READY / FULL SOURCE TREE NOT YET PUSHED

## Current verified local source
Exact R1 ZIP SHA-256:

`a1d95982626415e9589c133a95bf2cd2cac0d09ed8c92afe0368388494ec2654`

## Verified locally
- Python compile PASS.
- Critical backend HTTP journey PASS.
- Database contract PASS.
- Windows launcher contract PASS.
- ZIP integrity PASS.

## R1 launcher correction
- Launcher remains visible.
- Separate `RUN_BACKEND.bat` removes fragile nested cmd quoting.
- Startup and backend logs are written.
- Backend health is checked before browser open.
- Manual URL fallback is displayed.

## Important truth
The GitHub connector currently available in this chat cannot upload the whole generated local source tree in one operation. Do not treat this branch as the complete R1 application source yet. The exact R1 ZIP remains the current verified source snapshot until the tree is transferred.

No production deployment or production merge is claimed.
