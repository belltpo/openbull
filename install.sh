#!/usr/bin/env bash
set -Eeuo pipefail

# OpenBull live deployment entrypoint.
# Run on Ubuntu/Debian server:
#   chmod +x install.sh
#   sudo ./install.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${OPENBULL_DEPLOY_LOG_DIR:-/var/log/openbull}"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_DIR="$SCRIPT_DIR/logs"
  mkdir -p "$LOG_DIR"
fi
DEPLOY_LOG="$LOG_DIR/deploy_$TIMESTAMP.log"

log_info()  { echo -e "${GREEN}[INFO]${NC} $*" | tee -a "$DEPLOY_LOG"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$DEPLOY_LOG"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$DEPLOY_LOG"; }
log_step()  { echo -e "\n${CYAN}=== $* ===${NC}" | tee -a "$DEPLOY_LOG"; }

on_error() {
  local line="$1"
  log_error "Deployment failed at line $line. Log: $DEPLOY_LOG"
}
trap 'on_error "$LINENO"' ERR

prompt_default() {
  local prompt="$1"
  local default="$2"
  local value=""
  read -r -p "$prompt [$default]: " value
  printf '%s' "${value:-$default}"
}

prompt_yes_no() {
  local prompt="$1"
  local default="${2:-y}"
  local suffix="[y/N]"
  local value=""
  if [[ "$default" =~ ^[Yy]$ ]]; then
    suffix="[Y/n]"
  fi
  while true; do
    read -r -p "$prompt $suffix: " value
    value="${value:-$default}"
    case "$value" in
      y|Y|yes|YES) return 0 ;;
      n|N|no|NO) return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

run_cmd() {
  log_info "+ $*"
  "$@" 2>&1 | tee -a "$DEPLOY_LOG"
}

default_repo_url() {
  git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || printf '%s' "https://github.com/belltpo/openbull.git"
}

default_branch() {
  git -C "$SCRIPT_DIR" branch --show-current 2>/dev/null || printf '%s' "main"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_error "Missing required command: $1"
    exit 1
  fi
}

normalize_public_url() {
  local value="$1"
  if [[ "$value" =~ ^https?:// ]]; then
    printf '%s' "$value"
  else
    printf 'https://%s' "$value"
  fi
}

domain_host_from_value() {
  local value="$1"
  value="${value#https://}"
  value="${value#http://}"
  value="${value%%/*}"
  value="${value%%:*}"
  printf '%s' "$value"
}

default_ssl_email() {
  local host
  local apex
  host="$(domain_host_from_value "$1")"
  apex="$(awk -F. '{ if (NF >= 2) print $(NF-1) "." $NF; else print $0 }' <<<"$host")"
  printf 'admin@%s' "$apex"
}

validate_email() {
  [[ "$1" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]
}

print_header() {
  echo -e "${BLUE}"
  echo "OpenBull Live Deployment"
  echo "Single command installer/updater for Ubuntu production servers"
  echo -e "${NC}"
  echo "Log file: $DEPLOY_LOG"
  echo ""
}

collect_common_inputs() {
  DEFAULT_REPO="$(default_repo_url)"
  DEFAULT_BRANCH="$(default_branch)"

  DOMAIN="$(prompt_default "Live domain or public URL" "openbull.example.com")"
  PUBLIC_URL="$(normalize_public_url "$DOMAIN")"
  DEFAULT_SSL_EMAIL="$(default_ssl_email "$DOMAIN")"
  while true; do
    SSL_EMAIL="$(prompt_default "Email for SSL certificate notifications" "$DEFAULT_SSL_EMAIL")"
    if validate_email "$SSL_EMAIL"; then
      break
    fi
    echo "Please enter a valid email address."
  done
  REPO_URL="$(prompt_default "Git repository URL" "$DEFAULT_REPO")"
  REPO_BRANCH="$(prompt_default "Git branch to deploy" "$DEFAULT_BRANCH")"
  APP_ROOT="$(prompt_default "Server app directory" "/var/www/openbull")"
  SERVICE_NAME="$(prompt_default "Systemd service name" "openbull")"
  NODE_VERSION="$(prompt_default "Node.js major version" "20")"
  DB_HOST="$(prompt_default "PostgreSQL host" "localhost")"
  DB_PORT="$(prompt_default "PostgreSQL port" "5432")"
  DB_NAME="$(prompt_default "PostgreSQL database" "openbull")"
  DB_USER="$(prompt_default "PostgreSQL user" "postgres")"
  DB_PASSWORD="$(prompt_default "PostgreSQL password" "123456")"

  RUN_DEPS="no"
  RUN_MIGRATIONS="no"
  RUN_FRONTEND_BUILD="no"
  RUN_RESTART="no"
  RUN_NGINX_RELOAD="no"
  RUN_HEALTHCHECK="no"
  RUN_PERMISSIONS="no"

  if prompt_yes_no "Install/update Python and frontend dependencies" y; then RUN_DEPS="yes"; fi
  if prompt_yes_no "Run database migrations" y; then RUN_MIGRATIONS="yes"; fi
  if prompt_yes_no "Build frontend" y; then RUN_FRONTEND_BUILD="yes"; fi
  if prompt_yes_no "Fix app ownership/permissions for www-data" y; then RUN_PERMISSIONS="yes"; fi
  if prompt_yes_no "Restart OpenBull systemd service" y; then RUN_RESTART="yes"; fi
  if prompt_yes_no "Test and reload nginx" y; then RUN_NGINX_RELOAD="yes"; fi
  if prompt_yes_no "Run health check after deployment" y; then RUN_HEALTHCHECK="yes"; fi
}

env_value() {
  local file="$1"
  local key="$2"
  [[ -f "$file" ]] || return 0
  sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*['\"]?([^'\"]*)['\"]?[[:space:]]*$/\1/p" "$file" | head -1
}

existing_certbot_email() {
  local email=""
  if [[ -d /etc/letsencrypt/accounts ]]; then
    email="$(grep -Rho 'mailto:[A-Za-z0-9._%+-]*@[A-Za-z0-9.-]*' /etc/letsencrypt/accounts 2>/dev/null \
      | head -1 | sed 's/^mailto://' || true)"
  fi
  printf '%s' "$email"
}

collect_update_inputs() {
  # Update mode consumes the deployment that is already installed. It must not
  # ask for (or risk changing) domain/database values on every code release.
  APP_ROOT="${OPENBULL_APP_ROOT:-$SCRIPT_DIR}"
  if [[ ! -d "$APP_ROOT/.git" ]]; then
    APP_ROOT="/var/www/openbull"
  fi
  if [[ ! -d "$APP_ROOT/.git" ]]; then
    log_error "No existing OpenBull Git checkout found. Use Fresh install mode."
    exit 1
  fi

  DEFAULT_REPO="$(git -C "$APP_ROOT" remote get-url origin 2>/dev/null || default_repo_url)"
  DEFAULT_BRANCH="$(git -C "$APP_ROOT" branch --show-current 2>/dev/null || true)"
  REPO_URL="${OPENBULL_REPO_URL:-$DEFAULT_REPO}"
  REPO_BRANCH="${OPENBULL_REPO_BRANCH:-${DEFAULT_BRANCH:-main}}"
  SERVICE_NAME="${OPENBULL_SERVICE_NAME:-openbull}"
  NODE_VERSION="${OPENBULL_NODE_VERSION:-20}"

  local env_file="$APP_ROOT/.env"
  local frontend_url
  frontend_url="$(env_value "$env_file" FRONTEND_URL)"
  if [[ -n "$frontend_url" && "$frontend_url" =~ ^https?:// ]]; then
    DOMAIN="$frontend_url"
  else
    local nginx_domain=""
    nginx_domain="$(grep -RhsE '^[[:space:]]*server_name[[:space:]]+' /etc/nginx/sites-enabled 2>/dev/null \
      | sed -E 's/.*server_name[[:space:]]+([^ ;]+).*/\1/' | grep -v '^_$' | head -1 || true)"
    DOMAIN="${nginx_domain:-openbull.example.com}"
  fi
  PUBLIC_URL="$(normalize_public_url "$DOMAIN")"
  SSL_EMAIL="${OPENBULL_SSL_EMAIL:-$(existing_certbot_email)}"
  SSL_EMAIL="${SSL_EMAIL:-$(default_ssl_email "$DOMAIN")}"

  # These values are informational during an update; the existing .env stays
  # authoritative and is backed up before any build/restart operation.
  DB_HOST="existing .env"
  DB_PORT=""
  DB_NAME="preserved"
  DB_USER="preserved"
  DB_PASSWORD="preserved"

  RUN_DEPS="yes"
  RUN_MIGRATIONS="yes"
  RUN_FRONTEND_BUILD="yes"
  RUN_PERMISSIONS="yes"
  RUN_RESTART="yes"
  RUN_NGINX_RELOAD="yes"
  RUN_HEALTHCHECK="yes"
}

print_summary() {
  echo ""
  echo "Deployment summary"
  echo "  Mode:                  $DEPLOY_MODE"
  echo "  Public URL:            $PUBLIC_URL"
  echo "  SSL email:             $SSL_EMAIL"
  echo "  Repo:                  $REPO_URL"
  echo "  Branch:                $REPO_BRANCH"
  echo "  App root:              $APP_ROOT"
  echo "  Service:               $SERVICE_NAME"
  echo "  Node.js:               $NODE_VERSION"
  if [[ "$DEPLOY_MODE" == "update live" ]]; then
    echo "  Database/config:       preserve existing $APP_ROOT/.env"
  else
    echo "  Database:              $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
  fi
  echo "  Install deps:          $RUN_DEPS"
  echo "  Run migrations:        $RUN_MIGRATIONS"
  echo "  Build frontend:        $RUN_FRONTEND_BUILD"
  echo "  Fix permissions:       $RUN_PERMISSIONS"
  echo "  Restart service:       $RUN_RESTART"
  echo "  Reload nginx:          $RUN_NGINX_RELOAD"
  echo "  Health check:          $RUN_HEALTHCHECK"
  echo ""
}

export_for_child_installer() {
  export OPENBULL_REPO_URL="$REPO_URL"
  export OPENBULL_REPO_BRANCH="$REPO_BRANCH"
  export OPENBULL_APP_ROOT="$APP_ROOT"
  export OPENBULL_SERVICE_NAME="$SERVICE_NAME"
  export OPENBULL_NODE_VERSION="$NODE_VERSION"
  export OPENBULL_DB_HOST="$DB_HOST"
  export OPENBULL_DB_PORT="$DB_PORT"
  export OPENBULL_DB_NAME="$DB_NAME"
  export OPENBULL_DB_USER="$DB_USER"
  export OPENBULL_DB_PASSWORD="$DB_PASSWORD"
  export OPENBULL_SSL_EMAIL="$SSL_EMAIL"
}

fresh_install() {
  log_step "Fresh install"
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    log_error "Fresh install must be run with sudo because it installs packages, nginx, systemd, PostgreSQL, and SSL."
    exit 1
  fi
  export_for_child_installer
  local domain_host
  domain_host="$(domain_host_from_value "$PUBLIC_URL")"
  log_info "Running install/install.sh with the selected repo, branch, app root, service, and database values."
  printf '%s\n' "$domain_host" | bash "$SCRIPT_DIR/install/install.sh" 2>&1 | tee -a "$DEPLOY_LOG"
}

update_live() {
  log_step "Update live deployment"
  require_command git

  if [[ ! -d "$APP_ROOT/.git" ]]; then
    log_error "$APP_ROOT is not a git checkout. Use Fresh install mode first, or set the correct app directory."
    exit 1
  fi

  run_cmd git -C "$APP_ROOT" config --global --add safe.directory "$APP_ROOT"
  run_cmd git -C "$APP_ROOT" remote set-url origin "$REPO_URL"
  run_cmd git -C "$APP_ROOT" fetch origin "$REPO_BRANCH"
  run_cmd git -C "$APP_ROOT" checkout "$REPO_BRANCH"

  # Fresh installers and Windows-authored checkouts can leave harmless
  # line-ending/file-mode drift. Real server edits must also be preserved, not
  # overwritten. A named stash handles both and is deliberately not popped
  # over the newly deployed source.
  local stash_name="openbull-update-$TIMESTAMP"
  local dirty_status=""
  dirty_status="$(git -C "$APP_ROOT" status --porcelain --untracked-files=normal)"
  if [[ -n "$dirty_status" ]]; then
    local backup_dir="/var/backups/openbull/$TIMESTAMP"
    run_cmd mkdir -p "$backup_dir"
    git -C "$APP_ROOT" status --short > "$backup_dir/git-status.txt"
    git -C "$APP_ROOT" diff --binary > "$backup_dir/tracked-changes.patch"
    log_warn "Server checkout contains local changes; backing them up and stashing before update."
    log_info "Backup: $backup_dir"
    run_cmd git -C "$APP_ROOT" stash push --include-untracked -m "$stash_name"
    log_info "The stash is retained for manual recovery: git -C '$APP_ROOT' stash list"
  fi
  run_cmd git -C "$APP_ROOT" pull --ff-only origin "$REPO_BRANCH"

  if [[ -f "$APP_ROOT/.env" ]]; then
    run_cmd cp "$APP_ROOT/.env" "$APP_ROOT/.env.backup.$TIMESTAMP"
  fi

  if [[ "$RUN_DEPS" == "yes" ]]; then
    require_command uv
    log_step "Install Python dependencies"
    run_cmd bash -lc "cd '$APP_ROOT' && uv sync"
  fi

  if [[ "$RUN_MIGRATIONS" == "yes" ]]; then
    require_command uv
    log_step "Run migrations"
    if [[ -f "$APP_ROOT/migrate_all.py" ]]; then
      run_cmd bash -lc "cd '$APP_ROOT' && uv run python migrate_all.py"
    elif [[ -f "$APP_ROOT/alembic.ini" ]]; then
      run_cmd bash -lc "cd '$APP_ROOT' && uv run alembic upgrade head"
    else
      log_warn "No migrate_all.py or alembic.ini found. Skipping migrations."
    fi
  fi

  if [[ "$RUN_FRONTEND_BUILD" == "yes" ]]; then
    require_command npm
    log_step "Build frontend"
    if [[ -f "$APP_ROOT/frontend/package-lock.json" ]]; then
      run_cmd bash -lc "cd '$APP_ROOT/frontend' && npm ci"
    else
      run_cmd bash -lc "cd '$APP_ROOT/frontend' && npm install"
    fi
    run_cmd bash -lc "cd '$APP_ROOT/frontend' && npm run build"
  fi

  if [[ "$RUN_PERMISSIONS" == "yes" ]]; then
    log_step "Fix permissions"
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
      run_cmd chown -R www-data:www-data "$APP_ROOT"
      run_cmd chmod -R u=rwX,g=rX,o=rX "$APP_ROOT"
      if [[ -f "$APP_ROOT/.env" ]]; then
        run_cmd chmod 640 "$APP_ROOT/.env"
      fi
    else
      log_warn "Skipping permissions because this script is not running as root."
    fi
  fi

  if [[ "$RUN_RESTART" == "yes" ]]; then
    log_step "Restart service"
    run_cmd systemctl daemon-reload
    run_cmd systemctl restart "$SERVICE_NAME"
    if systemctl is-active --quiet "$SERVICE_NAME"; then
      log_info "$SERVICE_NAME is active."
    else
      log_error "$SERVICE_NAME is not active. Recent logs:"
      journalctl -u "$SERVICE_NAME" --no-pager -n 40 | tee -a "$DEPLOY_LOG" || true
      exit 1
    fi
  fi

  if [[ "$RUN_NGINX_RELOAD" == "yes" ]]; then
    log_step "Reload nginx"
    run_cmd nginx -t
    run_cmd systemctl reload nginx
  fi

  if [[ "$RUN_HEALTHCHECK" == "yes" ]]; then
    require_command curl
    log_step "Health check"
    if curl -fsS --max-time 20 "$PUBLIC_URL/health" | tee -a "$DEPLOY_LOG"; then
      log_info "Health check passed: $PUBLIC_URL/health"
    else
      log_warn "Health check failed. Check service/nginx logs."
    fi
  fi
}

build_check_only() {
  log_step "Build/check only"
  require_command uv
  require_command npm
  run_cmd bash -lc "cd '$SCRIPT_DIR' && uv run python -c 'import backend.main; print(\"backend import ok\")'"
  run_cmd bash -lc "cd '$SCRIPT_DIR/frontend' && npm run build"
}

print_header
echo "Choose action:"
echo "  1) Fresh install on this server"
echo "  2) Update existing live deployment"
echo "  3) Build/check current checkout only"
read -r -p "Select 1, 2, or 3 [2]: " MODE
MODE="${MODE:-2}"

case "$MODE" in
  1) DEPLOY_MODE="fresh install"; collect_common_inputs ;;
  2) DEPLOY_MODE="update live"; collect_update_inputs ;;
  3) DEPLOY_MODE="build/check only" ;;
  *) log_error "Invalid selection: $MODE"; exit 1 ;;
esac

if [[ "$MODE" != "3" ]]; then
  print_summary
  if ! prompt_yes_no "Proceed with these live deployment settings" n; then
    log_warn "Deployment cancelled."
    exit 0
  fi
fi

case "$MODE" in
  1) fresh_install ;;
  2) update_live ;;
  3) build_check_only ;;
esac

log_info "Done. Deployment log: $DEPLOY_LOG"
