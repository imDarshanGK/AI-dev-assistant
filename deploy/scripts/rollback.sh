#!/usr/bin/env bash
# =============================================================================
# rollback.sh — Manual / emergency rollback for the AI-dev-assistant service
#
# Usage:
#   ./deploy/scripts/rollback.sh [OPTIONS]
#
# Options:
#   -n, --namespace   <ns>       Kubernetes namespace         (default: default)
#   -d, --deployment  <name>     Deployment name              (default: qyverixai)
#   -u, --health-url  <url>      Service health endpoint base (default: http://localhost:8000)
#   -t, --timeout     <seconds>  Seconds to poll health after undo (default: 90)
#   -r, --revision    <number>   Roll back to a specific revision number
#                                (omit to go to the previous revision)
#   -h, --help                   Show this help text
#
# Exit codes:
#   0  — rollback completed and service is healthy
#   1  — rollback failed or service remains unhealthy after rollback
#
# Required tools: kubectl, curl
# =============================================================================

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
NAMESPACE="default"
DEPLOYMENT="qyverixai"
HEALTH_URL="http://localhost:8000"
TIMEOUT=90
REVISION=""

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

log_info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Argument parsing ──────────────────────────────────────────────────────────
usage() {
  sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--namespace)   NAMESPACE="$2";  shift 2 ;;
    -d|--deployment)  DEPLOYMENT="$2"; shift 2 ;;
    -u|--health-url)  HEALTH_URL="$2"; shift 2 ;;
    -t|--timeout)     TIMEOUT="$2";    shift 2 ;;
    -r|--revision)    REVISION="$2";   shift 2 ;;
    -h|--help)        usage ;;
    *) log_error "Unknown argument: $1"; usage ;;
  esac
done

# ── Pre-flight checks ─────────────────────────────────────────────────────────
for cmd in kubectl curl; do
  if ! command -v "$cmd" &>/dev/null; then
    log_error "Required tool not found: $cmd"
    exit 1
  fi
done

log_info "Target deployment : $DEPLOYMENT (namespace: $NAMESPACE)"
log_info "Health endpoint   : $HEALTH_URL/healthz/ready"
log_info "Poll timeout      : ${TIMEOUT}s"

# ── Capture current state before rollback ─────────────────────────────────────
CURRENT_IMAGE=$(kubectl get deployment/"$DEPLOYMENT" \
  -n "$NAMESPACE" \
  -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "unknown")
log_info "Current image     : $CURRENT_IMAGE"

# Show rollout history so the operator knows what they're rolling back to
log_info "Rollout history:"
kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE" 2>/dev/null || true
echo ""

# ── Perform the rollback ──────────────────────────────────────────────────────
if [[ -n "$REVISION" ]]; then
  log_info "Rolling back to revision $REVISION …"
  kubectl rollout undo deployment/"$DEPLOYMENT" \
    -n "$NAMESPACE" \
    --to-revision="$REVISION"
else
  log_info "Rolling back to the previous revision …"
  kubectl rollout undo deployment/"$DEPLOYMENT" \
    -n "$NAMESPACE"
fi

# ── Wait for the undo rollout to stabilise ────────────────────────────────────
log_info "Waiting for rollback rollout to complete …"
if ! kubectl rollout status deployment/"$DEPLOYMENT" \
     -n "$NAMESPACE" \
     --timeout=3m; then
  log_error "kubectl rollout status reported failure after rollback — pods may be stuck."
  log_warn  "Run: kubectl describe deployment/$DEPLOYMENT -n $NAMESPACE"
  exit 1
fi

# ── Annotate the rollback event ───────────────────────────────────────────────
ROLLED_BACK_TO_IMAGE=$(kubectl get deployment/"$DEPLOYMENT" \
  -n "$NAMESPACE" \
  -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "unknown")
log_ok "Rollout undo complete. Now running: $ROLLED_BACK_TO_IMAGE"

kubectl annotate deployment/"$DEPLOYMENT" \
  kubernetes.io/change-cause="ROLLBACK (manual rollback.sh): reverted from $CURRENT_IMAGE to $ROLLED_BACK_TO_IMAGE" \
  --overwrite \
  -n "$NAMESPACE" 2>/dev/null || true

# ── Health-check gate ─────────────────────────────────────────────────────────
READY_URL="${HEALTH_URL%/}/healthz/ready"
ELAPSED=0

log_info "Polling $READY_URL for up to ${TIMEOUT}s …"
while [[ "$ELAPSED" -lt "$TIMEOUT" ]]; do
  HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "$READY_URL" 2>/dev/null || echo "000")
  if [[ "$HTTP_CODE" == "200" ]]; then
    log_ok "Service is healthy (HTTP 200) after ${ELAPSED}s ✅"
    break
  fi
  log_warn "HTTP $HTTP_CODE — retrying in 5s (${ELAPSED}s / ${TIMEOUT}s elapsed)"
  sleep 5
  ELAPSED=$(( ELAPSED + 5 ))
done

if [[ "$ELAPSED" -ge "$TIMEOUT" ]]; then
  log_error "Service did NOT become healthy within ${TIMEOUT}s after rollback."
  log_warn  "The rollback image itself may be unhealthy. Investigate immediately:"
  log_warn  "  kubectl logs -l app=$DEPLOYMENT -n $NAMESPACE --tail=100"
  exit 1
fi

# ── Final summary ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Rollback completed successfully${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "  Reverted from : ${RED}$CURRENT_IMAGE${NC}"
echo -e "  Now running   : ${GREEN}$ROLLED_BACK_TO_IMAGE${NC}"
echo -e "  Health check  : ${GREEN}PASSED${NC}"
echo ""
