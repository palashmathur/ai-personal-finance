#!/usr/bin/env bash
#
# Regenerates the typed API client from the backend's live OpenAPI spec.
#
# The generated output (src/lib/api) is COMMITTED to git, so `npm run typecheck`
# works offline with no backend running. You only re-run this script when the
# backend's API surface changes (new endpoint, changed schema). The flow is:
#   1. start the backend  (make api)
#   2. cd apps/web && npm run gen:api
#   3. review the git diff, commit it
#
# Java analogy: this is like regenerating client stubs from a WSDL/Swagger spec
# — the server contract is the source of truth, the client types are derived.
set -euo pipefail

# Where the backend serves its OpenAPI document. Override with API_URL=... if the
# backend runs elsewhere.
API_URL="${API_URL:-http://localhost:8000}"
SPEC_URL="${API_URL}/openapi.json"
OUT_DIR="src/lib/api"

# Run from the apps/web directory regardless of where the script is invoked.
cd "$(dirname "$0")/.."

echo "Generating API client from ${SPEC_URL} -> ${OUT_DIR}"

# Fail early with a friendly message if the backend isn't reachable.
if ! curl -sf "${SPEC_URL}" -o /dev/null; then
  echo "ERROR: could not reach ${SPEC_URL}. Start the backend first (make api)." >&2
  exit 1
fi

# --client fetch    -> uses the browser fetch API, no axios dependency.
# --useOptions      -> service methods take a single named-options object
#                      ({ from, to, ... }) instead of long positional arg lists.
# --useUnionTypes   -> enums become string-literal unions ("buy" | "sell" | ...).
npx openapi-typescript-codegen \
  --input "${SPEC_URL}" \
  --output "${OUT_DIR}" \
  --client fetch \
  --useOptions \
  --useUnionTypes

echo "Done. Review the diff in ${OUT_DIR} and commit it."
