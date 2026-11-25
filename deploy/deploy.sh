#!/usr/bin/env bash
# Bring the whole AgroPilot stack up on this instance from the commit that is checked out.
#
# Run by the deploy workflow as the `ubuntu` user, after it has put the repo at the run's commit:
#   POSTGRES_PASSWORD=... bash deploy/deploy.sh
#
# Every step must work on a clean Ubuntu instance and on one that was already deployed many times:
# install only what is missing, write config files from scratch, never append.
set -euo pipefail

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is not set (Actions secret)}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICES="$ROOT/services"
UV="$HOME/.local/bin/uv"
NODE_DIR=/opt/node
NODE_LINE=latest-v24.x
PG_CONTAINER=agropilot-postgres
PG_VOLUME=agropilot-pgdata
PG_IMAGE=postgres:16
PG_DB=agropilot

step() { echo; echo "==> $*"; }

# ---------------------------------------------------------------------------------------------
step "System packages"
df -h / | tail -1 | awk '{print "Disk: " $4 " free of " $2}'
missing=()
command -v docker >/dev/null || missing+=(docker.io)
command -v curl >/dev/null || missing+=(curl)
command -v xz >/dev/null || missing+=(xz-utils)
if ((${#missing[@]})); then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}"
fi
sudo systemctl enable --now docker >/dev/null

if [ ! -x "$UV" ]; then
  echo "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
"$UV" --version

if [ ! -x "$NODE_DIR/bin/node" ]; then
  case "$(uname -m)" in
    x86_64) arch=x64 ;;
    aarch64) arch=arm64 ;;
    *) echo "Unsupported CPU: $(uname -m)" >&2; exit 1 ;;
  esac
  base="https://nodejs.org/dist/$NODE_LINE"
  line=$(curl -fsSL "$base/SHASUMS256.txt" | grep " node-v[0-9.]*-linux-$arch.tar.xz$")
  file=${line##* }
  tmp=$(mktemp -d)
  echo "Installing $file"
  curl -fsSL "$base/$file" -o "$tmp/$file"
  (cd "$tmp" && echo "$line" | sha256sum -c --quiet -)
  sudo rm -rf "$NODE_DIR" && sudo mkdir -p "$NODE_DIR"
  sudo tar -xJf "$tmp/$file" -C "$NODE_DIR" --strip-components=1
  rm -rf "$tmp"
fi
export PATH="$NODE_DIR/bin:$PATH"
echo "node $(node --version), npm $(npm --version)"

# ---------------------------------------------------------------------------------------------
step "PostgreSQL ($PG_IMAGE in Docker, data in volume $PG_VOLUME, port 5432 on 127.0.0.1 only)"
sudo docker volume create "$PG_VOLUME" >/dev/null
if sudo docker container inspect "$PG_CONTAINER" >/dev/null 2>&1; then
  sudo docker start "$PG_CONTAINER" >/dev/null
else
  # -e NAME without a value passes it from this environment, so the password is not on the command line.
  sudo --preserve-env=POSTGRES_PASSWORD docker run -d --name "$PG_CONTAINER" --restart unless-stopped \
    -e POSTGRES_PASSWORD -e POSTGRES_DB="$PG_DB" \
    -v "$PG_VOLUME":/var/lib/postgresql/data -p 127.0.0.1:5432:5432 "$PG_IMAGE" >/dev/null
fi
for _ in $(seq 1 60); do
  # -h 127.0.0.1: answer only once the real server is up, not the init-time one on the socket.
  sudo docker exec "$PG_CONTAINER" pg_isready -q -h 127.0.0.1 -U postgres -d "$PG_DB" && break
  sleep 1
done
sudo docker exec "$PG_CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d "$PG_DB"
# POSTGRES_PASSWORD only applies when the volume is first created; set it on every run so the secret
# stays the source of truth when it changes. Sent on stdin, quotes doubled for SQL.
printf "ALTER USER postgres PASSWORD '%s';\n" "${POSTGRES_PASSWORD//\'/\'\'}" |
  sudo docker exec -i "$PG_CONTAINER" psql -q -U postgres -d "$PG_DB" -v ON_ERROR_STOP=1

# ---------------------------------------------------------------------------------------------
step "Config files (written from scratch on every run)"
pg_password_url=$(python3 -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["POSTGRES_PASSWORD"], safe=""))')
umask 077
cat > "$SERVICES/registry-service/.env" <<EOF
DATABASE_URL=postgresql://postgres:$pg_password_url@127.0.0.1:5432/$PG_DB
AWS_REGION=us-east-1
AWS_S3_BUCKET=max-agropilot-photos
EOF
cat > "$SERVICES/weather-service/.env" <<'EOF'
PROVIDER_BASE_URL=https://api.open-meteo.com
PROVIDER_API_KEY=
PROVIDER_TIMEOUT_S=5
PROVIDER_RETRIES=2
PROVIDER_RETRY_BACKOFF_S=0.5
FORECAST_FRESH_HOURS=3
FORECAST_MAX_STALE_HOURS=24
RETRY_AFTER_S=60
EOF
cat > "$SERVICES/planner-service/.env" <<'EOF'
REGISTRY_URL=http://127.0.0.1:8000
WEATHER_URL=http://127.0.0.1:8001
REGISTRY_TIMEOUT_S=5
WEATHER_TIMEOUT_S=20
EOF
cat > "$SERVICES/frontend/.env.local" <<'EOF'
REGISTRY_URL=http://127.0.0.1:8000
WEATHER_URL=http://127.0.0.1:8001
PLANNER_URL=http://127.0.0.1:8002
EOF
umask 022
chmod 600 "$SERVICES/registry-service/.env"  # holds the database password, even if an older file was 644
echo "Wrote registry .env, weather .env, planner .env, frontend .env.local"

# ---------------------------------------------------------------------------------------------
step "Python services: locked runtime dependencies"
for service in registry-service weather-service planner-service; do
  (cd "$SERVICES/$service" && "$UV" sync --locked --no-dev)
done

step "Registry database: schema and seed on first run only"
status=0
(cd "$SERVICES/registry-service" && "$UV" run --no-sync python scripts/setup_db.py) || status=$?
case $status in
  0) echo "Created the schema and loaded the seed" ;;
  1) echo "Tables already exist: kept the data" ;;
  *) echo "setup_db.py failed (exit $status)" >&2; exit 1 ;;
esac

step "Frontend: install and production build"
(cd "$SERVICES/frontend" && npm ci --no-audit --no-fund && npm run build)

# ---------------------------------------------------------------------------------------------
step "systemd units"
units=(registry weather planner frontend)
sudo install -m 644 \
  "$SERVICES/registry-service/registry.service" \
  "$SERVICES/weather-service/weather.service" \
  "$SERVICES/planner-service/planner.service" \
  "$SERVICES/frontend/frontend.service" \
  /etc/systemd/system/
# A hand-made override from before the unit was in git; the committed unit is the whole truth now.
sudo rm -rf /etc/systemd/system/registry.service.d
sudo systemctl daemon-reload
for unit in "${units[@]}"; do
  sudo systemctl enable "$unit.service" >/dev/null 2>&1
  sudo systemctl restart "$unit.service"
done

# ---------------------------------------------------------------------------------------------
step "Health checks"
# restart returns before the app is up: wait for each one, else show its log and fail the deploy.
check() {
  local unit=$1 url=$2 seconds=$3
  for _ in $(seq 1 "$seconds"); do
    if curl -fsS -o /dev/null "$url"; then echo "$unit is healthy ($url)"; return 0; fi
    sleep 1
  done
  echo "$unit did not answer $url within $seconds s" >&2
  sudo journalctl -u "$unit.service" -n 30 --no-pager >&2
  return 1
}
check registry http://127.0.0.1:8000/health 30
check weather http://127.0.0.1:8001/health 30
check planner http://127.0.0.1:8002/health 30
check frontend http://127.0.0.1:3000/ 60
# The database too: a registry read goes through PostgreSQL.
curl -fsS -o /dev/null http://127.0.0.1:8000/v1/farms && echo "registry reads from PostgreSQL"

echo
echo "Deployed $(git -C "$ROOT" log -1 --format='%h %s')"
