#!/usr/bin/env bash
#
# Regenerate THIRD_PARTY_NOTICES.txt from the pinned dependency manifests.
# Run before every release — see "Publishing a new release" in
# GETTING_STARTED.md.
#
# Requires: backend/.venv set up from backend/requirements.txt, and
# ui/node_modules installed (npm ci).
#
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x backend/.venv/bin/pip ]; then
  echo "error: backend/.venv not found. Set up the backend venv first (see GETTING_STARTED.md)." >&2
  exit 1
fi
if [ ! -d ui/node_modules ]; then
  echo "error: ui/node_modules not found. Run 'npm ci' in ui/ first." >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

backend/.venv/bin/pip install --quiet pip-licenses
backend/.venv/bin/pip-licenses --format=json --with-urls > "$TMP/backend.json"

(cd ui && npx --yes license-checker --production --json --excludePrivatePackages) > "$TMP/frontend.json"

python3 - "$TMP/backend.json" "$TMP/frontend.json" THIRD_PARTY_NOTICES.txt <<'PYEOF'
import datetime
import json
import sys

backend_path, frontend_path, out_path = sys.argv[1:4]

backend_raw = json.load(open(backend_path))
seen = {}
for pkg in backend_raw:
    if pkg["Name"].lower() in ("pip-licenses", "prettytable", "wcwidth"):
        continue
    seen[pkg["Name"]] = pkg
backend = sorted(
    ((p["Name"], p["Version"], p["License"], p.get("URL") or "UNKNOWN") for p in seen.values()),
    key=lambda r: r[0].lower(),
)

frontend_raw = json.load(open(frontend_path))
frontend = []
for key, info in frontend_raw.items():
    name, _, version = key.rpartition("@")
    if not name:
        name, version = key, ""
    frontend.append((name, version, info.get("licenses", "UNKNOWN"), info.get("repository", "UNKNOWN")))
frontend.sort(key=lambda r: r[0].lower())


def render_table(rows):
    name_w = max(len(r[0]) for r in rows) + 2
    ver_w = max(len(r[1]) for r in rows) + 2
    lic_w = max(len(r[2]) for r in rows) + 2
    header = f"{'Package':<{name_w}}{'Version':<{ver_w}}{'License':<{lic_w}}Project"
    lines = [header, "-" * len(header)]
    for name, version, lic, url in rows:
        lines.append(f"{name:<{name_w}}{version:<{ver_w}}{lic:<{lic_w}}{url}")
    return "\n".join(lines)


with open(out_path, "w") as f:
    f.write("THIRD-PARTY NOTICES\n")
    f.write("====================\n\n")
    f.write(
        "Smart Data Frameworks (SDF), Community edition, includes the following\n"
        "third-party open source components. This list is generated from the\n"
        "pinned dependency manifests (backend/requirements.txt, ui/package.json)\n"
        "and covers every package installed into the published Docker image,\n"
        "either as an installed Python package or bundled into the compiled\n"
        "frontend assets. Referenced from NOTICE, item 6.\n\n"
    )
    f.write(
        "Each component is licensed under the terms noted below, as stated by\n"
        "that component's own package metadata. Those terms apply to that\n"
        "component; they do not alter the license under which SDF itself is\n"
        "distributed (see LICENSE).\n\n"
    )
    f.write(f"Generated: {datetime.date.today().isoformat()}, from backend\n")
    f.write(
        "requirements.txt (Python 3.11) and ui/package.json production\n"
        "dependencies. Regenerate on each release (see GETTING_STARTED.md).\n\n"
    )
    f.write("--------------------------------------------------------------------\n")
    f.write("Backend (Python)\n")
    f.write("--------------------------------------------------------------------\n\n")
    f.write(render_table(backend))
    f.write("\n\n")
    f.write("--------------------------------------------------------------------\n")
    f.write("Frontend (npm, production bundle)\n")
    f.write("--------------------------------------------------------------------\n\n")
    f.write(render_table(frontend))
    f.write("\n")
PYEOF

echo "Wrote THIRD_PARTY_NOTICES.txt"
