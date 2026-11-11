---
name: feedback-bash-errexit-subshell-or
description: In CI shell, `( set -e; ... ) || handler` never fails — bash ignores errexit on the left of ||/&&/if. Check each command explicitly and read back what landed.
metadata:
  type: feedback
---
The daily.yml R2 upload wrapped its uploads in `( set -e ... ) || { warn; FAILED=1; }`. Bash disables errexit for any command on the left of `||`, even with `set -e` inside the subshell. On the first prod upload (2026-11-11), every AccessDenied printed "Uploaded" and the step stayed green. Fixed in b3aee04.

**Why:** A green run that didn't deliver is a data-honesty failure. Vega and the Owner rely on the run status and the log text.
**How to apply:** In CI scripts, check each critical command with `if cmd; then ok; else record failure; fi` and exit non-zero at the end. Read back what landed (head-object / fetch) instead of trusting an echo. Test failure paths with a fake binary on PATH before pushing. Related: [[feedback-verify-live-matches-validated-rule]], [[helios-weekly-protocol-fix-2026-11-10]]
