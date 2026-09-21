#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?source dir required}"
BUILD_DIR="${2:?build dir required}"
STATE_JSON="${3:?state json required}"

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  echo "missing prepared Blender source: $SOURCE_DIR" >&2
  exit 2
fi

mkdir -p "$BUILD_DIR"
cd "$SOURCE_DIR"

if [[ "${CH_BLENDER_SKIP_UPDATE:-0}" != "1" ]]; then
  make update
fi

make release BUILD_DIR="$BUILD_DIR"

BLENDER_EXE="$BUILD_DIR/bin/blender"
test -x "$BLENDER_EXE"
VERSION_LINE="$($BLENDER_EXE --version | head -n 1)"
if [[ "$VERSION_LINE" != *"City Horizon Internal"* ]]; then
  echo "internal identity marker missing: $VERSION_LINE" >&2
  exit 3
fi

python3 - "$STATE_JSON" "$BLENDER_EXE" "$VERSION_LINE" <<'PY'
import hashlib, json, pathlib, sys
state_path = pathlib.Path(sys.argv[1])
exe = pathlib.Path(sys.argv[2])
version_line = sys.argv[3]
h = hashlib.sha256()
with exe.open('rb') as f:
    for block in iter(lambda: f.read(1024*1024), b''):
        h.update(block)
source = json.loads(state_path.read_text())
out = {
    'contract': 'CH_BLENDER_INTERNAL_BUILD_STATE_V1',
    'status': 'ok',
    'patchsetId': source['patchsetId'],
    'upstreamCommit': source['upstreamCommit'],
    'versionLine': version_line,
    'executable': str(exe),
    'executableSha256': h.hexdigest(),
    'rendererModified': False,
    'blendFileFormatModified': False,
}
path = state_path.parent / 'ch_blender_internal_build_state.json'
path.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
print(json.dumps(out, indent=2, sort_keys=True))
PY
