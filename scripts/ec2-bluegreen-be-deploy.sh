#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <ec2-host> <ec2-user> <dockerhub-user> <tag> [ssh-key-path]"
  echo "Required env: DATABASE_URL"
  echo "Optional env: CORS_ALLOW_ORIGINS"
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL env is required"
  exit 1
fi

EC2_HOST="$1"
EC2_USER="$2"
DOCKERHUB_USER="$3"
TAG="$4"
SSH_KEY_PATH="${5:-}"
CORS_ALLOW_ORIGINS="${CORS_ALLOW_ORIGINS:-}"

SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_KEY_PATH" ]]; then
  SSH_OPTS+=(-i "$SSH_KEY_PATH")
fi

ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" \
  "DOCKERHUB_USER='${DOCKERHUB_USER}' TAG='${TAG}' DATABASE_URL='${DATABASE_URL}' CORS_ALLOW_ORIGINS='${CORS_ALLOW_ORIGINS}' bash -s" <<'REMOTE_EOF'
set -euo pipefail

REMOTE_DIR="$HOME/community-be-bluegreen"
NETWORK_NAME="community-be-bg-net"
PROXY_CONTAINER="community-be-proxy"
ACTIVE_SLOT_FILE="$REMOTE_DIR/active_slot"

if ! command -v docker >/dev/null 2>&1; then
  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y docker
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y docker
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y docker.io
  else
    echo "Unsupported package manager: cannot install docker" >&2
    exit 1
  fi
fi

sudo systemctl enable --now docker
mkdir -p "$REMOTE_DIR/nginx"

if ! sudo docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
  sudo docker network create "$NETWORK_NAME" >/dev/null
fi

ACTIVE_SLOT="blue"
if [[ -f "$ACTIVE_SLOT_FILE" ]]; then
  ACTIVE_SLOT="$(cat "$ACTIVE_SLOT_FILE")"
fi

NEXT_SLOT="green"
if [[ "$ACTIVE_SLOT" == "green" ]]; then
  NEXT_SLOT="blue"
fi

NEXT_CONTAINER="community-be-${NEXT_SLOT}"
ACTIVE_CONTAINER="community-be-${ACTIVE_SLOT}"
IMAGE="${DOCKERHUB_USER}/community-backend:${TAG}"

echo "[1/7] Pull image: $IMAGE"
sudo docker pull "$IMAGE" >/dev/null

echo "[2/7] Start next slot container: ${NEXT_CONTAINER}"
sudo docker rm -f "$NEXT_CONTAINER" >/dev/null 2>&1 || true

RUN_ARGS=(
  --name "$NEXT_CONTAINER"
  --restart unless-stopped
  --network "$NETWORK_NAME"
  -e DATABASE_URL="$DATABASE_URL"
)

if [[ -n "$CORS_ALLOW_ORIGINS" ]]; then
  RUN_ARGS+=(-e CORS_ALLOW_ORIGINS="$CORS_ALLOW_ORIGINS")
fi

sudo docker run -d "${RUN_ARGS[@]}" "$IMAGE" >/dev/null

echo "[3/7] Health check next slot"
for i in $(seq 1 45); do
  if sudo docker run --rm --network "$NETWORK_NAME" curlimages/curl:8.12.1 -fsS "http://${NEXT_CONTAINER}:8000/health" >/dev/null; then
    HEALTH_OK="true"
    break
  fi
  HEALTH_OK="false"
  sleep 2
done

if [[ "${HEALTH_OK}" != "true" ]]; then
  echo "Next slot health check failed: ${NEXT_CONTAINER}" >&2
  sudo docker logs "$NEXT_CONTAINER" --tail 200 || true
  exit 1
fi

echo "[4/7] Switch Nginx upstream to ${NEXT_CONTAINER}"
cat > "$REMOTE_DIR/nginx/default.conf" <<NGINX_CONF
server {
  listen 80;
  server_name _;

  client_max_body_size 20m;

  location /health {
    proxy_pass http://${NEXT_CONTAINER}:8000/health;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
  }

  location / {
    proxy_pass http://${NEXT_CONTAINER}:8000;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
  }
}
NGINX_CONF

if ! sudo docker ps -a --format '{{.Names}}' | grep -qx "$PROXY_CONTAINER"; then
  sudo docker run -d \
    --name "$PROXY_CONTAINER" \
    --restart unless-stopped \
    --network "$NETWORK_NAME" \
    -p 80:80 \
    -v "$REMOTE_DIR/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" \
    nginx:1.27-alpine >/dev/null
else
  sudo docker start "$PROXY_CONTAINER" >/dev/null
  sudo docker exec "$PROXY_CONTAINER" nginx -s reload >/dev/null
fi

echo "[5/7] Persist active slot"
echo "$NEXT_SLOT" > "$ACTIVE_SLOT_FILE"

echo "[6/7] Keep previous slot for rollback readiness: ${ACTIVE_CONTAINER}"
if [[ "$ACTIVE_CONTAINER" != "$NEXT_CONTAINER" ]]; then
  sudo docker ps --format '{{.Names}}' | grep -qx "$ACTIVE_CONTAINER" && echo "Previous slot running: ${ACTIVE_CONTAINER}" || true
fi

echo "[7/7] Result"
echo "Active slot: $(cat "$ACTIVE_SLOT_FILE")"
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | grep -E '^community-be-|^community-be-proxy' || true
REMOTE_EOF
