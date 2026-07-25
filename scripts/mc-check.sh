#!/usr/bin/env bash
# Compile every engine translation unit with ../mc (TinyCC) and report a
# pass/fail matrix. See TRANSITION_PLAN.md Phase 2, Item 0.
#
# Usage:
#   scripts/mc-check.sh [build-dir] [-- file-substring ...]
#
# build-dir defaults to `build`, falling back to the first `build*` directory
# that contains a compile_commands.json. Pass one or more substrings after
# `--` to restrict the check to matching source paths.
#
# Requires ../mc/build/mc (relative to the repo root) and a configured Meson
# build directory (`meson setup <dir>`) so compile_commands.json carries the
# real include/define flags for every TU, including vendored dependencies.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

mc_bin="$repo_root/../mc/build/mc"
if [[ ! -x "$mc_bin" ]]; then
  echo "error: $mc_bin not found or not executable (build ../mc first)" >&2
  exit 2
fi

build_dir=""
filters=()

for arg in "$@"; do
  if [[ "$arg" == "--" ]]; then
    shift_seen=1
    continue
  fi
  if [[ -z "${shift_seen:-}" && -z "$build_dir" ]]; then
    build_dir="$arg"
  else
    filters+=("$arg")
  fi
done

if [[ -z "$build_dir" ]]; then
  if [[ -f build/compile_commands.json ]]; then
    build_dir="build"
  else
    build_dir="$(ls -d build*/ 2>/dev/null | head -1 | sed 's#/$##')"
  fi
fi

if [[ -z "$build_dir" || ! -f "$build_dir/compile_commands.json" ]]; then
  echo "error: no compile_commands.json found (run 'meson setup <dir>' first)" >&2
  exit 2
fi

echo "using build dir: $build_dir"
echo "using mc: $mc_bin"
echo

results_file="$(mktemp)"
trap 'rm -f "$results_file"' EXIT

python3 - "$build_dir/compile_commands.json" "${filters[@]}" <<'PYEOF' > "$results_file"
import json
import shlex
import sys

cc_path = sys.argv[1]
filters = sys.argv[2:]

with open(cc_path) as f:
    entries = json.load(f)

# Engine sources only: src/**/*.c, excluding vendor/, main.c, and .cc (Item 1
# is a separate migration; numbers.cc is not yet a valid mc target).
seen = set()
for entry in entries:
    file = entry["file"]
    norm = file.lstrip("./")
    if norm.startswith("../"):
        norm = norm[3:]
    if not norm.startswith("src/"):
        continue
    if norm.endswith(".cc") or norm.endswith(".cpp"):
        continue
    if not norm.endswith(".c"):
        continue
    if norm == "src/main.c":
        continue
    if filters and not any(f in norm for f in filters):
        continue
    if norm in seen:
        continue
    seen.add(norm)

    args = shlex.split(entry["command"])
    flags = []
    skip_next = False
    for a in args[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in ("-o", "-MF", "-MQ", "-MT"):
            skip_next = True
            continue
        if a == "-c" or a.startswith("-I") or a.startswith("-D") or a.startswith("-U"):
            flags.append(a)
            continue
        if a.startswith("-std="):
            flags.append(a)
            continue
    print(json.dumps({"file": norm, "directory": entry["directory"], "flags": flags}))
PYEOF

pass_count=0
fail_count=0
declare -a failed_files=()

while IFS= read -r line; do
  file=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['file'])" "$line")
  directory=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['directory'])" "$line")
  mapfile -t flags < <(python3 -c "import json,sys; [print(x) for x in json.loads(sys.argv[1])['flags']]" "$line")

  if (cd "$directory" && "$mc_bin" build "${flags[@]}" -o /dev/null "$repo_root/$file" >/tmp/mc-check-out.$$ 2>&1); then
    echo "PASS  $file"
    pass_count=$((pass_count + 1))
  else
    echo "FAIL  $file"
    sed 's/^/      /' /tmp/mc-check-out.$$ | head -5
    fail_count=$((fail_count + 1))
    failed_files+=("$file")
  fi
  rm -f /tmp/mc-check-out.$$
done < "$results_file"

echo
echo "== mc-check summary: $pass_count passed, $fail_count failed =="
if [[ $fail_count -gt 0 ]]; then
  printf 'failed: %s\n' "${failed_files[@]}"
  exit 1
fi
