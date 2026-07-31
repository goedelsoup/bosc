#!/usr/bin/env bash
#
# rotate.sh — secret rotation for the watermark-deploy Pulumi stack (#1539).
#
# Wraps the set-secret → apply → verify sequence so a rotation is one command instead of a
# checklist. The *ordering* it can't do for you (issue the new value upstream first; revoke
# the old one only after production verifies) is the whole point of SECRETS.md — read that
# before rotating anything shared, especially TURNSTILE_SECRET_KEY.
#
#   ./rotate.sh list                       # the inventory: config key → Pages env var
#   ./rotate.sh set <configKey>            # prompt (or read stdin) → pulumi up → verify
#   ./rotate.sh turnstile                  # Cloudflare rotate_secret → pulumi up --refresh → verify
#   ./rotate.sh verify [--deep]            # post-deploy check; safe to run any time
#
# Values are never passed as arguments — they arrive on stdin and go to Pulumi on stdin, so
# they stay out of shell history and out of `ps`.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# The Pulumi config namespace is the PROJECT name, not the S3 state prefix. Read it from
# Pulumi.yaml rather than hardcoding, so a future rename can't silently strand every key.
NAMESPACE="$(sed -n 's/^name:[[:space:]]*//p' Pulumi.yaml | head -1)"
[[ -n "$NAMESPACE" ]] || { echo "rotate: could not read the project name from Pulumi.yaml" >&2; exit 1; }

ASSUME_YES=""
DEEP=""
URL_OVERRIDE=""

# --- the inventory ----------------------------------------------------------------------
# configKey|PAGES_ENV_VAR|multiline|what it is. Pulumi-provisioned and wrangler-set secrets
# have no config key and are not settable here (see SECRETS.md for those).
SECRETS=(
  "anthropicApiKey|ANTHROPIC_API_KEY|no|Claude API key — /api/ask"
  "honeycombApiKey|HONEYCOMB_API_KEY|no|Honeycomb ingest key — edge OTel + /api/rum"
  "tipsAppId|TIPS_APP_ID|no|GitHub App id — /api/submit (not actually secret; does not rotate)"
  "tipsAppPrivateKey|TIPS_APP_PRIVATE_KEY|yes|GitHub App private key, PKCS#8 PEM — /api/submit"
  "earlyAccessSecret|EARLY_ACCESS_SECRET|no|HMAC key for the __ea pre-launch cookie"
  "storiesLakebaseUrl|(Hyperdrive origin)|no|Lakebase postgres:// URL — stories/contacts + notify"
  "githubWebhookSecret|(Lambda env)|no|GitHub webhook signing secret — lambda/notify"
  "unsubSecret|(Lambda env)|no|Unsubscribe-link signing secret — lambda/notify"
)

secret_field() { # <configKey> <1-based field>
  local row
  for row in "${SECRETS[@]}"; do
    [[ "${row%%|*}" == "$1" ]] || continue
    cut -d'|' -f"$2" <<<"$row"
    return 0
  done
  return 1
}

die() { echo "rotate: $*" >&2; exit 1; }
note() { echo "  $*"; }

# curl with a bearer token that never reaches argv. `-H "Authorization: Bearer $TOKEN"`
# would put the token in the process table for anyone running `ps` — unacceptable in a tool
# whose whole job is handling credentials. curl reads extra options from a config file, and
# `--config -` takes that file on stdin, so the header stays in the pipe.
#   curl_auth <token> <remaining curl args…>
curl_auth() {
  local token="$1"
  shift
  printf 'header = "Authorization: Bearer %s"\n' "$token" | curl --config - "$@"
}

# The usage text IS the header comment above — print it back rather than keeping a second
# copy that drifts. Stops at the first line that isn't a comment.
usage() {
  awk 'NR<3 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "${BASH_SOURCE[0]}"
}

# --- list -------------------------------------------------------------------------------
cmd_list() {
  printf '%-22s %-24s %s\n' "CONFIG KEY" "PAGES ENV VAR" "WHAT IT IS"
  local row
  for row in "${SECRETS[@]}"; do
    IFS='|' read -r key env _ desc <<<"$row"
    printf '%-22s %-24s %s\n' "$key" "$env" "$desc"
  done
  cat <<EOF

Set one with:  ./rotate.sh set <config key>      (namespace: ${NAMESPACE})

Not settable here — different mechanisms, see SECRETS.md:
  TURNSTILE_SECRET_KEY   Pulumi-provisioned  ./rotate.sh turnstile
  ASK_PLUGIN_TOKEN       wrangler-set        cd ../web && wrangler pages secret put ASK_PLUGIN_TOKEN
  CLOUDFLARE_API_TOKEN   GitHub Actions secret
EOF
}

# --- set --------------------------------------------------------------------------------
cmd_set() {
  local key="${1:-}"
  [[ -n "$key" ]] || die "usage: ./rotate.sh set <config key>   (./rotate.sh list)"
  secret_field "$key" 1 >/dev/null || die "unknown config key '$key' — run ./rotate.sh list"

  local multiline env_var
  multiline="$(secret_field "$key" 3)"
  env_var="$(secret_field "$key" 2)"

  # Capture the value. Piped/redirected stdin wins; otherwise prompt without echo. A
  # multi-line value (the PKCS#8 PEM) can't come from a no-echo prompt, so require a file.
  local tmp
  tmp="$(mktemp)"
  # shellcheck disable=SC2064  # expand $tmp now, at trap-set time
  trap "rm -f '$tmp'" EXIT

  if [[ ! -t 0 ]]; then
    cat > "$tmp"
  elif [[ "$multiline" == "yes" ]]; then
    die "$key is multi-line — pipe it in:  ./rotate.sh set $key < key.pkcs8.pem"
  else
    local value
    read -rsp "New value for ${NAMESPACE}:${key} (not echoed): " value
    echo
    printf '%s' "$value" > "$tmp"
  fi
  [[ -s "$tmp" ]] || die "empty value — nothing set"

  # Single-line values pick up a stray newline from every pipe going; strip it. Multi-line
  # PEMs keep theirs (the trailing newline is part of the armour). Rewritten through a shell
  # variable rather than a second temp file: a `$tmp.trimmed` would sit outside the EXIT
  # trap, so an interrupt between writing it and moving it would strand the plaintext secret.
  if [[ "$multiline" != "yes" ]]; then
    local trimmed
    trimmed="$(tr -d '\r\n' < "$tmp")"
    printf '%s' "$trimmed" > "$tmp"
  fi

  echo "==> pulumi config set --secret ${NAMESPACE}:${key}"
  pulumi config set --secret "${NAMESPACE}:${key}" < "$tmp"
  rm -f "$tmp"
  trap - EXIT

  echo "==> pulumi up"
  # shellcheck disable=SC2086  # $ASSUME_YES is a deliberate optional flag
  pulumi up $ASSUME_YES

  echo "==> verifying"
  cmd_verify || {
    echo
    echo "VERIFY FAILED — do NOT revoke the old value yet." >&2
    echo "If the Pages project carries the new value but the live endpoint does not, cut a" >&2
    echo "fresh deployment (.github/workflows/pages.yml, deploy: true) and re-verify." >&2
    return 1
  }

  cat <<EOF

Rotation applied and verified.

  Next: revoke the OLD value at its provider — that step closes the overlap window and is
  the one nothing here can do for you. ${env_var} · see SECRETS.md for the per-secret
  correctness check to run before revoking.
EOF
}

# --- turnstile --------------------------------------------------------------------------
cmd_turnstile() {
  local account sitekey
  account="$(pulumi config get "${NAMESPACE}:cloudflareAccountId" </dev/null 2>/dev/null || true)"
  [[ -n "$account" ]] || die "could not read ${NAMESPACE}:cloudflareAccountId from the stack config"
  [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]] || die "CLOUDFLARE_API_TOKEN is not set (needs Turnstile Sites: Write)"
  # `|| true` so a pulumi failure doesn't trip `set -e` before the check below can print the
  # actionable message — same pattern as the read-only lookups in cmd_verify.
  sitekey="$(pulumi stack output turnstileSiteKey </dev/null 2>/dev/null || true)"
  [[ -n "$sitekey" ]] || die "could not read the turnstileSiteKey stack output"

  cat <<EOF
About to rotate the Turnstile secret for sitekey ${sitekey}.

  This secret gates BOTH /api/submit and /api/ask. The old secret stays valid for TWO HOURS
  and CANNOT be rotated again within that window — the whole sequence below must finish
  before it expires or both forms start failing verification. Read SECRETS.md first.

EOF
  if [[ -z "$ASSUME_YES" ]]; then
    local reply
    read -rp "Proceed? [y/N] " reply
    [[ "$reply" == [yY] ]] || die "aborted"
  fi

  echo "==> POST rotate_secret (invalidate_immediately=false → 2h overlap)"
  curl_auth "$CLOUDFLARE_API_TOKEN" -fsS -X POST \
    "https://api.cloudflare.com/client/v4/accounts/${account}/challenges/widgets/${sitekey}/rotate_secret" \
    -H 'Content-Type: application/json' \
    -d '{"invalidate_immediately": false}' > /dev/null

  # --refresh is load-bearing: without it Pulumi still holds the pre-rotation secret in
  # state and `up` would write the stale value straight back over the new one.
  echo "==> pulumi up --refresh"
  # shellcheck disable=SC2086
  pulumi up --refresh $ASSUME_YES

  echo "==> verifying"
  cmd_verify
}

# --- verify -----------------------------------------------------------------------------
# Two independent tiers: what the Pages PROJECT carries (Cloudflare API) and what the live
# DEPLOYMENT actually serves (endpoint probe). They fail differently and both matter.
cmd_verify() {
  local failures=0

  # Tier 1 — project config. Best-effort: skipped, not failed, without a token or jq, so
  # `verify` still works for anyone who can reach the site but not the Cloudflare account.
  local account project
  account="$(pulumi config get "${NAMESPACE}:cloudflareAccountId" </dev/null 2>/dev/null || true)"
  project="$(pulumi config get "${NAMESPACE}:pagesProject" </dev/null 2>/dev/null || echo "the-watermark-directory")"
  if [[ -n "${CLOUDFLARE_API_TOKEN:-}" && -n "$account" ]] && command -v jq >/dev/null; then
    echo "-- Pages project env vars (${project})"
    local body
    body="$(curl_auth "$CLOUDFLARE_API_TOKEN" -fsS \
      "https://api.cloudflare.com/client/v4/accounts/${account}/pages/projects/${project}")" || body=""
    if [[ -z "$body" ]]; then
      note "SKIP  could not read the project (token scope?)"
    else
      local name vartype
      for name in TURNSTILE_SECRET_KEY ANTHROPIC_API_KEY TIPS_APP_ID TIPS_APP_PRIVATE_KEY; do
        vartype="$(jq -r --arg n "$name" \
          '.result.deployment_configs.production.env_vars[$n].type // "absent"' <<<"$body")"
        if [[ "$vartype" == "secret_text" ]]; then
          note "ok    ${name} (secret_text)"
        elif [[ "$vartype" == "absent" ]]; then
          note "FAIL  ${name} is not on the project — did pulumi up run?"
          failures=$((failures + 1))
        else
          note "FAIL  ${name} is type '${vartype}', expected secret_text"
          failures=$((failures + 1))
        fi
      done
    fi
  else
    echo "-- Pages project env vars: SKIP (needs CLOUDFLARE_API_TOKEN, the account id, and jq)"
  fi

  # Tier 2 — live behaviour. Both endpoints return 500 {"error":"endpoint is misconfigured"}
  # when a required secret is missing, and check that BEFORE parsing the body — so an empty
  # probe payload is enough to tell "secrets present" from "secrets missing". Any other
  # status (400/401/403/503) means the env landed; only that specific 500 is a failure.
  local url
  url="${URL_OVERRIDE:-${WATERMARK_SITE_URL:-$(pulumi stack output siteUrl </dev/null 2>/dev/null || echo "https://the.watermark.directory")}}"
  echo "-- live endpoints (${url})"
  local path
  for path in /api/ask /api/submit; do
    local out code
    out="$(curl -sS -m 30 -o - -w '\n%{http_code}' -X POST "${url}${path}" \
      -H 'Content-Type: application/json' -d '{}' 2>/dev/null || true)"
    code="$(tail -n1 <<<"$out")"
    if [[ -z "$code" ]]; then
      note "FAIL  ${path} unreachable"
      failures=$((failures + 1))
    elif [[ "$code" == "500" ]] && grep -q 'endpoint is misconfigured' <<<"$out"; then
      note "FAIL  ${path} 500 endpoint is misconfigured — a required secret is absent"
      failures=$((failures + 1))
    else
      note "ok    ${path} HTTP ${code} (not a misconfigured 500)"
    fi
  done

  # --deep — the only tier that proves a value is CORRECT rather than merely present. Needs
  # ASK_PLUGIN_TOKEN, the bearer that stands in for Turnstile on /api/ask (#1578).
  if [[ -n "$DEEP" ]]; then
    echo "-- deep check: a real /api/ask round-trip"
    if [[ -z "${ASK_PLUGIN_TOKEN:-}" ]]; then
      note "SKIP  ASK_PLUGIN_TOKEN not set — check /ask by hand in a browser instead"
    else
      local out code
      out="$(curl_auth "$ASK_PLUGIN_TOKEN" -sS -m 60 -o - -w '\n%{http_code}' -X POST "${url}/api/ask" \
        -H 'Content-Type: application/json' \
        -d '{"question":"What does this site document?"}' 2>/dev/null || true)"
      code="$(tail -n1 <<<"$out")"
      case "$code" in
        200)
          note "ok    /api/ask answered — ANTHROPIC_API_KEY is valid, not just present" ;;
        # 503 is a GATE, not a bad key: ASK_ENABLED off, or the fail-closed budget guard
        # (#587 — no ASK_BUDGET/ASK_RATE_LIMIT KV bound and ASK_ALLOW_UNCAPPED!="true").
        # Either way the request never reaches Anthropic, so the key is untested — say so
        # rather than reporting a failure the operator can't act on. Observed on prod.
        503)
          note "SKIP  /api/ask is gated (503) — kill switch or the fail-closed budget guard;"
          note "      the key was never exercised. Check /ask by hand once the gate is open." ;;
        403)
          note "FAIL  /api/ask rejected the bearer (403) — ASK_PLUGIN_TOKEN does not match"
          failures=$((failures + 1)) ;;
        *)
          note "FAIL  /api/ask returned HTTP ${code} to an authorized request"
          failures=$((failures + 1)) ;;
      esac
    fi
  fi

  [[ "$failures" -eq 0 ]] || return 1
  echo "verify: OK"
}

# --- dispatch ---------------------------------------------------------------------------
COMMAND=""
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) ASSUME_YES="--yes" ;;
    --deep)   DEEP="1" ;;
    --url)    [[ $# -ge 2 ]] || die "--url needs a value"; URL_OVERRIDE="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)       die "unknown flag '$1'" ;;
    *)        if [[ -z "$COMMAND" ]]; then COMMAND="$1"; else ARGS+=("$1"); fi ;;
  esac
  shift
done

case "$COMMAND" in
  list)      cmd_list ;;
  set)       cmd_set "${ARGS[0]:-}" ;;
  turnstile) cmd_turnstile ;;
  verify)    cmd_verify ;;
  ""|help)   usage ;;
  *)         die "unknown command '$COMMAND' — try: list | set | turnstile | verify" ;;
esac
