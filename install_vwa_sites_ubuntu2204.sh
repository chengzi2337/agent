#!/usr/bin/env bash
set -euo pipefail

DEFAULT_HOME="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
REPO_DIR="${VWA_REPO_DIR:-$DEFAULT_HOME/visualwebarena}"
VENV_DIR="${VWA_VENV_DIR:-$DEFAULT_HOME/.venvs/visualwebarena}"
ASSET_DIR="${VWA_ASSET_DIR:-$DEFAULT_HOME/vwa_assets}"
CLASSIFIEDS_DIR="${VWA_CLASSIFIEDS_DIR:-$DEFAULT_HOME/classifieds_docker_compose}"
FALLBACK_DOCKER_SOCK="${VWA_DOCKER_SOCK:-/mnt/wsl/docker-desktop-bind-mounts/Ubuntu/docker.sock}"
HOSTNAME_VALUE="${VWA_HOSTNAME:-localhost}"
CLASSIFIEDS_TOKEN="${VWA_CLASSIFIEDS_RESET_TOKEN:-4b61655535e7ed388f0d40a93600254c}"
STEP="${1:-all}"

CLASSIFIEDS_ZIP="${ASSET_DIR}/classifieds_docker_compose.zip"
REDDIT_TAR="${ASSET_DIR}/postmill-populated-exposed-withimg.tar"
SHOPPING_TAR="${ASSET_DIR}/shopping_final_0712.tar"
WIKI_ZIM="${ASSET_DIR}/wikipedia_en_all_maxi_2022-05.zim"

log() {
  printf '[VWA sites] %s\n' "$1"
}

need_file() {
  if [ ! -e "$1" ]; then
    printf 'Missing required path: %s\n' "$1" >&2
    exit 1
  fi
}

ensure_docker_host() {
  if [ -S /var/run/docker.sock ]; then
    return
  fi

  if [ -S "$FALLBACK_DOCKER_SOCK" ]; then
    export DOCKER_HOST="unix://$FALLBACK_DOCKER_SOCK"
    return
  fi

  printf 'No Docker daemon socket found. Checked /var/run/docker.sock and %s\n' "$FALLBACK_DOCKER_SOCK" >&2
  exit 1
}

load_python_env() {
  need_file "$VENV_DIR/bin/activate"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

ensure_prereqs() {
  ensure_docker_host
  mkdir -p "$ASSET_DIR"

  if ! command -v unzip >/dev/null 2>&1; then
    log "Installing unzip"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y unzip
  fi
}

download_file() {
  local output_path="$1"
  shift

  if [ -s "$output_path" ]; then
    log "Using existing asset $(basename "$output_path")"
    return
  fi

  local url
  for url in "$@"; do
    log "Downloading $(basename "$output_path") from $url"
    if wget -c -O "$output_path" "$url"; then
      return
    fi
    log "Download failed for $url"
    rm -f "$output_path"
  done

  printf 'Failed to download %s from all mirrors.\n' "$output_path" >&2
  exit 1
}

download_classifieds() {
  ensure_prereqs
  download_file \
    "$CLASSIFIEDS_ZIP" \
    "https://archive.org/download/classifieds_docker_compose/classifieds_docker_compose.zip"
}

download_reddit() {
  ensure_prereqs
  download_file \
    "$REDDIT_TAR" \
    "https://archive.org/download/postmill-populated-exposed-withimg/postmill-populated-exposed-withimg.tar"
}

download_shopping() {
  ensure_prereqs
  download_file \
    "$SHOPPING_TAR" \
    "http://metis.lti.cs.cmu.edu/webarena-images/shopping_final_0712.tar"
}

download_wikipedia() {
  ensure_prereqs
  download_file \
    "$WIKI_ZIM" \
    "http://metis.lti.cs.cmu.edu/webarena-images/wikipedia_en_all_maxi_2022-05.zim"
}

download_assets() {
  download_classifieds
  download_reddit
  download_shopping
  download_wikipedia
}

prepare_classifieds() {
  ensure_prereqs

  if [ ! -d "$CLASSIFIEDS_DIR" ]; then
    log "Unpacking classifieds compose bundle"
    rm -rf "$CLASSIFIEDS_DIR"
    unzip -q "$CLASSIFIEDS_ZIP" -d "$DEFAULT_HOME"
  fi

  local compose_file="${CLASSIFIEDS_DIR}/docker-compose.yml"
  need_file "$compose_file"

  python3 - <<PY
from pathlib import Path

compose_path = Path("$compose_file")
text = compose_path.read_text(encoding="utf-8")
text = text.replace("http://<your-server-hostname>:9980/", "http://$HOSTNAME_VALUE:9980/")
text = text.replace("4b61655535e7ed388f0d40a93600254c", "$CLASSIFIEDS_TOKEN")
compose_path.write_text(text, encoding="utf-8")
PY
}

load_images() {
  ensure_prereqs

  if ! docker image inspect shopping_final_0712 >/dev/null 2>&1; then
    log "Loading shopping image"
    docker load --input "$SHOPPING_TAR"
  fi

  if ! docker image inspect postmill-populated-exposed-withimg >/dev/null 2>&1; then
    log "Loading reddit image"
    docker load --input "$REDDIT_TAR"
  fi
}

start_classifieds() {
  prepare_classifieds
  local compose_dir="${CLASSIFIEDS_DIR}"
  log "Starting classifieds via docker compose"
  docker compose -f "${compose_dir}/docker-compose.yml" up --build -d
  log "Waiting for classifieds database to be ready"
  sleep 20
  docker exec classifieds_db mysql -u root -ppassword osclass -e 'source docker-entrypoint-initdb.d/osclass_craigslist.sql'
}

start_reddit() {
  load_images
  if docker ps -a --format '{{.Names}}' | grep -qx forum; then
    docker rm -f forum >/dev/null 2>&1 || true
  fi
  log "Starting reddit/forum container"
  docker run --name forum -p 9999:80 -d postmill-populated-exposed-withimg
}

start_shopping() {
  load_images
  if docker ps -a --format '{{.Names}}' | grep -qx shopping; then
    docker rm -f shopping >/dev/null 2>&1 || true
  fi
  log "Starting shopping container"
  docker run --name shopping -p 7770:80 -d shopping_final_0712
  log "Waiting for shopping to boot"
  sleep 60
  docker exec shopping /var/www/magento2/bin/magento setup:store-config:set --base-url="http://${HOSTNAME_VALUE}:7770"
  docker exec shopping mysql -u magentouser -pMyPassword magentodb -e "UPDATE core_config_data SET value='http://${HOSTNAME_VALUE}:7770/' WHERE path = 'web/secure/base_url';"
  docker exec shopping /var/www/magento2/bin/magento cache:flush
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule catalogrule_product
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule catalogrule_rule
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule catalogsearch_fulltext
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule catalog_category_product
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule customer_grid
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule design_config_grid
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule inventory
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule catalog_product_category
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule catalog_product_attribute
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule catalog_product_price
  docker exec shopping /var/www/magento2/bin/magento indexer:set-mode schedule cataloginventory_stock
}

start_wikipedia() {
  ensure_prereqs
  mkdir -p "${ASSET_DIR}/wikipedia"
  cp -f "$WIKI_ZIM" "${ASSET_DIR}/wikipedia/"
  if docker ps -a --format '{{.Names}}' | grep -qx wikipedia; then
    docker rm -f wikipedia >/dev/null 2>&1 || true
  fi
  log "Starting wikipedia container"
  docker run -d --name wikipedia --volume="${ASSET_DIR}/wikipedia:/data" -p 8888:80 ghcr.io/kiwix/kiwix-serve:3.3.0 wikipedia_en_all_maxi_2022-05.zim
}

start_homepage() {
  need_file "$REPO_DIR/environment_docker/webarena-homepage/app.py"
  load_python_env
  local homepage_dir="${REPO_DIR}/environment_docker/webarena-homepage"
  local index_file="${homepage_dir}/templates/index.html"
  python3 - <<PY
from pathlib import Path

index_path = Path("$index_file")
text = index_path.read_text(encoding="utf-8")
text = text.replace("<your-server-hostname>", "$HOSTNAME_VALUE")
index_path.write_text(text, encoding="utf-8")
PY

  if pgrep -f "flask run --host=0.0.0.0 --port=4399" >/dev/null 2>&1; then
    pkill -f "flask run --host=0.0.0.0 --port=4399" || true
    sleep 2
  fi

  log "Starting homepage flask app"
  nohup bash -lc "cd '$homepage_dir' && FLASK_APP=app.py flask run --host=0.0.0.0 --port=4399" >"$DEFAULT_HOME/vwa_homepage.log" 2>&1 &
  sleep 5
}

start_all() {
  start_classifieds
  start_reddit
  start_shopping
  start_wikipedia
  start_homepage
}

smoke() {
  python3 - <<PY
import requests

targets = [
    ("CLASSIFIEDS", "http://$HOSTNAME_VALUE:9980"),
    ("SHOPPING", "http://$HOSTNAME_VALUE:7770"),
    ("REDDIT", "http://$HOSTNAME_VALUE:9999"),
    ("WIKIPEDIA", "http://$HOSTNAME_VALUE:8888"),
    ("HOMEPAGE", "http://$HOSTNAME_VALUE:4399"),
]

for name, url in targets:
    try:
        response = requests.get(url, timeout=15)
        print(f"{name}: {response.status_code} {url}")
    except Exception as exc:
        print(f"{name}: ERROR {url} -> {exc}")
PY
}

probe_shopping() {
  local asset_bytes=""
  local asset_present="false"
  local image_present="false"
  local image_bytes=""

  if [ -f "$SHOPPING_TAR" ]; then
    asset_present="true"
    asset_bytes="$(stat -c %s "$SHOPPING_TAR")"
  fi

  if command -v docker >/dev/null 2>&1; then
    if [ -S /var/run/docker.sock ] || [ -S "$FALLBACK_DOCKER_SOCK" ]; then
      ensure_docker_host
      if docker image inspect shopping_final_0712 >/dev/null 2>&1; then
        image_present="true"
        image_bytes="$(docker image inspect shopping_final_0712 --format '{{.Size}}')"
      fi
    fi
  fi

  python3 - <<PY
def humanize(raw):
    if not raw:
        return "missing"
    value = float(raw)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"

print("site=shopping")
print("asset_present=$asset_present")
print(f"asset_size_bytes={'$asset_bytes' or 'missing'}")
print(f"asset_size_human={humanize('$asset_bytes')}")
print("docker_image_present=$image_present")
print(f"docker_image_size_bytes={'$image_bytes' or 'missing'}")
print(f"docker_image_size_human={humanize('$image_bytes')}")
print("estimated_container_count=1")
print("startup_wait_seconds=60")
print("post_start_configuration_steps=11")
print("first_start_complexity=high")
PY
}

case "$STEP" in
  download)
    download_assets
    ;;
  download-classifieds)
    download_classifieds
    ;;
  download-reddit)
    download_reddit
    ;;
  download-shopping)
    download_shopping
    ;;
  download-wikipedia)
    download_wikipedia
    ;;
  prepare-classifieds)
    prepare_classifieds
    ;;
  load-images)
    load_images
    ;;
  start-classifieds)
    start_classifieds
    ;;
  start-reddit)
    start_reddit
    ;;
  start-shopping)
    start_shopping
    ;;
  start-wikipedia)
    start_wikipedia
    ;;
  start-homepage)
    start_homepage
    ;;
  start-all)
    start_all
    ;;
  smoke)
    smoke
    ;;
  probe-shopping)
    probe_shopping
    ;;
  all)
    download_assets
    start_all
    smoke
    ;;
  *)
    printf 'Usage: %s {download|download-classifieds|download-reddit|download-shopping|download-wikipedia|prepare-classifieds|load-images|start-classifieds|start-reddit|start-shopping|start-wikipedia|start-homepage|start-all|smoke|probe-shopping|all}\n' "$0" >&2
    exit 1
    ;;
esac
