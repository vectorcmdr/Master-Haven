#!/usr/bin/env bash
# =====================================================================
# Phase 4 end-to-end test
# =====================================================================
# Exercises the full draft -> publish flow per the build prompt:
#   1. Log in as diplomat (Watcher, seeded id=3)
#   2. Create a new brief draft
#   3. Auto-save (PATCH body)
#   4. Submit for review
#   5. Switch login to editor (TheKeeper, seeded id=8, is_editor=1)
#   6. Mark ready
#   7. Switch back to diplomat
#   8. Publish
#   9. Confirm new story in /stories
#  10. Confirm draft no longer shows in /drafts (status='published')
#  11. Confirm audit_log has the relevant entries (admin login: Ekimo id=1)
#
# Usage:
#   BASE_URL=http://pi8gb:8020 ./tests/test_phase4.sh
# Defaults to http://pi8gb:8020. No external deps beyond bash + curl.

set -euo pipefail

BASE_URL="${BASE_URL:-http://pi8gb:8020}"
API="$BASE_URL/api/v1"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

# Seeded user IDs from app/seed.py (insertion order):
DIPLOMAT_ID=3       # Watcher (base_role=diplomat, no editor flag)
EDITOR_ID=8         # TheKeeper (base_role=historian, is_editor=1)
ADMIN_ID=1          # Ekimo (is_admin=1)

# --- tiny helpers -----------------------------------------------------
pass() { printf "  \033[32mPASS\033[0m  %s\n" "$1"; }
fail() { printf "  \033[31mFAIL\033[0m  %s\n" "$1"; exit 1; }
step() { printf "\n\033[1m== %s ==\033[0m\n" "$1"; }

# Pull a value out of JSON by key. Naive — works for the shapes we
# return (no nested objects on the same line, no escaped quotes).
# Usage: get_json '"id":' "$json"  -> first integer after "id":
get_int() {
    echo "$2" | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*-?[0-9]+" | head -1 | grep -oE -- "-?[0-9]+\$"
}
get_str() {
    echo "$2" | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 | sed -E "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"([^\"]*)\".*/\1/"
}

login_as() {
    local uid="$1"
    rm -f "$COOKIE_JAR"
    local resp
    resp=$(curl -sS -c "$COOKIE_JAR" -X POST "$API/auth/dev/login" \
        -H "Content-Type: application/json" \
        -d "{\"user_id\": $uid}")
    local got
    got=$(get_int id "$resp")
    [ "$got" = "$uid" ] || fail "login as user $uid failed: $resp"
}

req() {
    # req METHOD PATH [JSON_BODY]
    local method="$1" path="$2" body="${3:-}"
    if [ -n "$body" ]; then
        curl -sS -b "$COOKIE_JAR" -X "$method" "$API$path" \
            -H "Content-Type: application/json" -d "$body"
    else
        curl -sS -b "$COOKIE_JAR" -X "$method" "$API$path"
    fi
}

req_status() {
    # req_status METHOD PATH [JSON_BODY]  -> prints HTTP code only
    local method="$1" path="$2" body="${3:-}"
    if [ -n "$body" ]; then
        curl -sS -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" \
            -X "$method" "$API$path" \
            -H "Content-Type: application/json" -d "$body"
    else
        curl -sS -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" \
            -X "$method" "$API$path"
    fi
}

# --- run --------------------------------------------------------------

step "0. Sanity: /health"
HEALTH=$(curl -sS "$BASE_URL/health")
echo "  $HEALTH"
[ "$(get_str status "$HEALTH")" = "ok" ] || fail "health check did not return ok"
pass "API is reachable"

step "1. Login as diplomat (Watcher, id=$DIPLOMAT_ID)"
login_as "$DIPLOMAT_ID"
ME=$(req GET /auth/me)
DIPLOMAT_NAME=$(get_str display_name "$ME")
pass "logged in as: $DIPLOMAT_NAME"

step "2. Create a new brief draft"
CREATE_BODY='{"doctype":"brief","headline":"Test draft from phase 4","beat":"projects","civs":["voyagers-haven"]}'
DRAFT=$(req POST /drafts "$CREATE_BODY")
DRAFT_ID=$(get_int id "$DRAFT")
[ -n "$DRAFT_ID" ] || fail "no draft id in response: $DRAFT"
pass "draft created: id=$DRAFT_ID"

step "3. Auto-save (PATCH with body)"
PATCH_BODY='{"body":"This is the body of the test draft. Auto-saved by PATCH.","deck":"Test deck"}'
PATCHED=$(req PATCH "/drafts/$DRAFT_ID" "$PATCH_BODY")
[ "$(get_str status "$PATCHED")" = "draft" ] || fail "draft status after patch wrong: $PATCHED"
pass "draft body auto-saved"

step "4. Submit for review"
SUBMITTED=$(req POST "/drafts/$DRAFT_ID/submit")
[ "$(get_str status "$SUBMITTED")" = "in_review" ] || fail "expected status=in_review: $SUBMITTED"
pass "draft submitted (status=in_review)"

step "5. Switch login to editor (TheKeeper, id=$EDITOR_ID)"
login_as "$EDITOR_ID"
EDITOR_NAME=$(get_str display_name "$(req GET /auth/me)")
pass "logged in as: $EDITOR_NAME"

step "6. Mark ready"
READY=$(req POST "/drafts/$DRAFT_ID/mark_ready")
[ "$(get_str status "$READY")" = "ready" ] || fail "expected status=ready: $READY"
pass "draft marked ready"

step "7. Switch login back to diplomat"
login_as "$DIPLOMAT_ID"
pass "logged back in as: $(get_str display_name "$(req GET /auth/me)")"

step "8. Publish"
PUBLISHED=$(req POST "/drafts/$DRAFT_ID/publish")
[ "$(get_str status "$PUBLISHED")" = "published" ] || fail "expected status=published: $PUBLISHED"
STORY_ID=$(get_int published_as_story_id "$PUBLISHED")
[ -n "$STORY_ID" ] || fail "no published_as_story_id in response: $PUBLISHED"
pass "draft published (story_id=$STORY_ID)"

step "9. Confirm new story exists"
STORY=$(curl -sS "$API/stories/$STORY_ID")
HEADLINE=$(get_str headline "$STORY")
[ "$HEADLINE" = "Test draft from phase 4" ] || fail "story headline wrong: $STORY"
pass "story exists with correct headline"

step "10. Confirm draft no longer shows in personal /drafts"
login_as "$DIPLOMAT_ID"
DRAFTS_LIST=$(req GET "/drafts?view=personal")
# The list excludes status='published', so our draft_id should not appear
if echo "$DRAFTS_LIST" | grep -qE "\"id\"[[:space:]]*:[[:space:]]*$DRAFT_ID\b"; then
    fail "published draft still appears in /drafts list: $DRAFTS_LIST"
fi
pass "published draft is hidden from /drafts list"

step "11. Confirm audit_log has the relevant entries (login as admin)"
login_as "$ADMIN_ID"
AUDIT=$(req GET "/admin/audit_log?target_type=draft&target_id=$DRAFT_ID")
# Expected actions: draft.create, draft.submit, draft.mark_ready, draft.publish
for action in draft.create draft.submit draft.mark_ready draft.publish; do
    if ! echo "$AUDIT" | grep -q "\"action\"[[:space:]]*:[[:space:]]*\"$action\""; then
        fail "audit_log missing action: $action — got: $AUDIT"
    fi
done
pass "audit_log has draft.create / submit / mark_ready / publish for draft_id=$DRAFT_ID"

echo
echo "=================================================="
echo "  PHASE 4 END-TO-END TEST PASSED"
echo "=================================================="
