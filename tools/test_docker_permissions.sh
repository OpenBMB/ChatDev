#!/bin/sh
# Build first: docker build --target runtime -t chatdev-permissions-test .
# Run: sh tools/test_docker_permissions.sh chatdev-permissions-test
set -eu
image=${1:?Pass the runtime image to test}
volume="chatdev-permissions-$$"
container="chatdev-permissions-$$"
cleanup() {
    docker rm -f "$container" >/dev/null 2>&1 || true
    docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 1' INT TERM

docker volume create "$volume" >/dev/null
# Docker copies /app from the image into the new volume. Emulate a Linux
# root-owned checkout independently of Docker Desktop's host file sharing.
docker run --rm --user root -v "$volume:/app" --entrypoint sh "$image" -c '
    chown -R root:root /app
    chmod 755 /app
    mkdir -p /app/data
    printf preserved > /app/data/existing.txt
'
# Reproduce the original failure with the image's default non-root user.
docker run --rm -v "$volume:/app" --entrypoint python "$image" -c '
import os
from pathlib import Path
assert os.getuid() != 0
try:
    Path("WareHouse").mkdir()
except PermissionError:
    print("Reproduced: non-root backend cannot create WareHouse")
else:
    raise AssertionError("Expected the original permission failure")
'
# The Compose init service runs this exact entrypoint; check repeatability.
for iteration in 1 2; do
    docker run --rm --user root -v "$volume:/app" --entrypoint python "$image" /usr/local/bin/init-runtime-dirs.py
done
docker run --rm -v "$volume:/app" --entrypoint python "$image" -c '
import os
import sqlite3
from pathlib import Path
assert os.getuid() != 0
assert Path("server_main.py").stat().st_uid == 0
assert Path("data/existing.txt").read_text() == "preserved"
for name in ("WareHouse", "logs", "data"):
    (Path(name) / "permission-test.txt").write_text("writable")
with sqlite3.connect("data/permissions.db") as db:
    db.execute("CREATE TABLE smoke (value TEXT)")
print("Storage writable, existing data preserved, source ownership unchanged")
'
docker run -d --name "$container" -v "$volume:/app" "$image" >/dev/null
ready=false
for attempt in $(seq 1 60); do
    if docker exec "$container" python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:6400/docs", timeout=2)' >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
if [ "$ready" != true ]; then
    docker logs "$container"
    exit 1
fi
docker exec "$container" python -c '
from server.services.vuegraphs_storage import save_vuegraph_content, fetch_vuegraph_content
save_vuegraph_content("permissions-test.yaml", "preserved workflow")
assert fetch_vuegraph_content("permissions-test.yaml") == "preserved workflow"
'
printf '%s\n' 'PASS: backend starts as non-root and workflow database is writable'
