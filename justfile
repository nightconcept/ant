msys2_root := env_var_or_default('MSYS2_ROOT', 'C:/msys64')

export PATH := if os() == 'windows' { msys2_root + "/clang64/bin;" + msys2_root + "/usr/bin;" + env_var('PATH') } else { env_var('PATH') }
export CC := if os() == 'windows' { msys2_root + "/clang64/bin/clang.exe" } else { env_var_or_default('CC', 'cc') }
export CXX := if os() == 'windows' { msys2_root + "/clang64/bin/clang++.exe" } else { env_var_or_default('CXX', 'c++') }

platform_flags := if os() == 'windows' { "-Dc_std=gnu2x" } else { "" }
bootstrap_command := if os() == 'windows' { "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap-windows.ps1" } else { "echo Build prerequisites are managed by the host system." }

default: build

# Download subprojects and configure build directory
setup:
    {{bootstrap_command}}
    meson setup build --wipe {{platform_flags}}

# Configure build directory without JIT
no_jit:
    meson setup build --wipe -Djit=false {{platform_flags}}

# Configure build directory with AddressSanitizer
asan:
    meson setup build --wipe -Db_sanitize=address -Doptimization=0 -Db_lto=false -Dstrip=false -Db_lundef=false {{platform_flags}}

# Configure build directory for debug
debug:
    meson setup build --wipe --buildtype=debug -Doptimization=0 -Db_lto=false -Dstrip=false -Db_lundef=false -Dunity=off {{platform_flags}}

# Compile Ant executable
build:
    meson compile -C build

# Reconfigure Meson build
reconfigure:
    meson setup --reconfigure build

# Strip debug symbols from binary
strip:
    meson compile -C build
    strip build/ant

# Download GitHub artifacts
download:
    .github/download.sh
    open .github/artifacts

# Build and run a JS file or binary with arguments
run +args="":
    meson compile -C build
    ./build/ant {{args}}

# Run full preflight agent checks
preflight:
    ./build/ant .github/agents/check_all.js

# Check repository knowledge docs
knowledge:
    ./build/ant .github/agents/check_repo_knowledge.js

# Check repository structure invariants
structure:
    ./build/ant .github/agents/check_repo_structure.js

# Route and report recommended validation for git changes
validate_changes:
    ./build/ant .github/agents/route_validation.js

# Run shell environment
shell:
    mise run shell

# Run spec tests
test:
    meson compile -C build
    ./build/ant examples/spec/run.js

# Run the full benchmark suite (26 benchmarks, 5 runtimes, ~5 min)
bench +args="":
    python3 bench/bench.py {{args}}

# Fast tier for edit-test loops: 15 benchmarks, ant/txiki.js/node, ~85s.
# Same workloads as the full suite, so it diffs against the same baseline.
bench-fast +args="":
    python3 bench/bench.py --fast {{args}}

# Fast tier, then diff against the checked-in baseline. The everyday check.
bench-fast-diff +args="":
    -python3 bench/bench.py --fast {{args}}
    python3 scripts/bench_baseline.py diff .deps/compliance/logs/bench-latest.json

# Full run recorded to the history series - intended for the nightly cron.
# Does not touch the baseline; use bench-update-baseline to move that.
bench-nightly +args="":
    python3 bench/bench.py {{args}}
    python3 scripts/bench_baseline.py record .deps/compliance/logs/bench-latest.json

# Run compliance benchmark suite across runtimes
bench-compliance +args="":
    python3 bench/compliance.py --allow-failures {{args}}

# Run compliance across runtimes (ant/txiki.js/node/deno/bun), no persistence
compliance-runtimes +args="":
    python3 bench/compliance.py --allow-failures {{args}}

# Full clean cross-runtime compliance run, then promote it to the checked-in snapshot (informational, not a CI gate)
compliance-runtimes-update +args="":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "error: working tree is dirty - refusing to update the compliance-runtimes baseline from an unreproducible run." >&2
        exit 1
    fi
    python3 bench/compliance.py --allow-failures --update-baseline {{args}}

# Run the benchmarks and record them in the history, leaving the baseline alone
bench-record +args="":
    python3 bench/bench.py {{args}}
    python3 scripts/bench_baseline.py record .deps/compliance/logs/bench-latest.json

# Run the benchmarks and diff them against the checked-in baseline
bench-diff +args="":
    -python3 bench/bench.py {{args}}
    python3 scripts/bench_baseline.py diff .deps/compliance/logs/bench-latest.json

# Full clean benchmark run, then promote it to the checked-in baseline
bench-update-baseline +args="":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "error: working tree is dirty - refusing to update the bench baseline from an unreproducible run." >&2
        exit 1
    fi
    python3 bench/bench.py {{args}}
    python3 scripts/bench_baseline.py update .deps/compliance/logs/bench-latest.json

# Print the recorded benchmark series (no run)
bench-history +args="":
    python3 scripts/bench_baseline.py history {{args}}

# Pretty-print the checked-in compliance + bench baselines (no fresh run)
dashboard +args="":
    python3 scripts/dashboard.py {{args}}

# Run compliance test suites (generic escape hatch; prefer named recipes below)
compliance +args="":
    meson compile -C build
    python3 scripts/run_compliance.py {{args}}

# Run the pinned WinterTC/WPT suite.
compliance-wintertc:
    meson compile -C build
    -python3 scripts/run_compliance.py --suite wintertc --all --log-fail

# Run all Ant-owned regression tests.
compliance-regression:
    meson compile -C build
    -python3 scripts/run_compliance.py --suite regression --all --log-fail

# Run the pinned Test262 corpus. ~50k tests, expect this to take a while.
compliance-test262:
    @echo "Running the full Test262 suite (~50k tests) - this takes a while."
    meson compile -C build
    -python3 scripts/run_compliance.py --suite test262 --all --log-fail

# Full clean WinterTC run, then promote its manifest to the checked-in baseline
compliance-update-wintertc:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "error: working tree is dirty - refusing to update the WinterTC baseline from an unreproducible run." >&2
        exit 1
    fi
    meson compile -C build
    python3 scripts/run_compliance.py --suite wintertc --all --allow-failures --log-fail
    python3 scripts/compliance_baseline.py update .deps/compliance/logs/wintertc-latest.json

# Full clean Ant Regression run, then promote its manifest to the checked-in baseline
compliance-update-regression:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "error: working tree is dirty - refusing to update the Regression baseline from an unreproducible run." >&2
        exit 1
    fi
    meson compile -C build
    python3 scripts/run_compliance.py --suite regression --all --log-fail
    python3 scripts/compliance_baseline.py update .deps/compliance/logs/regression-latest.json

# Full clean Test262 run (~50k tests), then promote its manifest
compliance-update-test262:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "error: working tree is dirty - refusing to update the Test262 baseline from an unreproducible run." >&2
        exit 1
    fi
    echo "Running the full Test262 suite (~50k tests) - this takes a while."
    meson compile -C build
    python3 scripts/run_compliance.py --suite test262 --all --allow-failures --log-fail
    python3 scripts/compliance_baseline.py update .deps/compliance/logs/test262-latest.json

# Run WinterTC and diff the resulting manifest against the checked-in baseline
compliance-diff-wintertc:
    meson compile -C build
    -python3 scripts/run_compliance.py --suite wintertc --all --log-fail
    python3 scripts/compliance_baseline.py diff .deps/compliance/logs/wintertc-latest.json

# Run Ant Regression and diff the resulting manifest against the checked-in baseline
compliance-diff-regression:
    meson compile -C build
    -python3 scripts/run_compliance.py --suite regression --all --log-fail
    python3 scripts/compliance_baseline.py diff .deps/compliance/logs/regression-latest.json

# Run Test262 and diff the resulting manifest against the checked-in baseline
compliance-diff-test262:
    @echo "Running the full Test262 suite (~50k tests) - this takes a while."
    meson compile -C build
    -python3 scripts/run_compliance.py --suite test262 --all --log-fail
    python3 scripts/compliance_baseline.py diff .deps/compliance/logs/test262-latest.json


# Fetch upstream and report incoming commits plus which of our commits they collide with
upstream-status branch="dev":
    python3 scripts/sync_upstream.py status --branch {{branch}}

# Three-way Test262 comparison across a merge: pre-merge, merged, upstream standalone.
# Run this from the sync branch. See docs/repo/upstream-sync.md.
upstream-verify base="dev":
    #!/usr/bin/env bash
    set -euo pipefail
    work=".deps/sync"
    # Every run is measured against one pinned Test262 checkout - a fresh clone
    # picks up new tests and reports corpus growth as merge regressions.
    if [ ! -d .deps/compliance/test262 ]; then
        echo "error: no Test262 checkout to pin. Run 'just compliance-test262' once first." >&2
        exit 1
    fi
    for name in base upstream; do
        git worktree remove --force "$work/$name" 2>/dev/null || true
    done
    rm -rf "$work"; mkdir -p "$work"

    meson compile -C build
    cp build/ant "$work/ant-merged"
    # The upstream worktree has no compliance harness of its own - it is a
    # fork-only addition, so every suite runs from this tree with the binary
    # under test swapped in, and the merged binary restored afterwards.
    restore() { cp "$work/ant-merged" build/ant 2>/dev/null || true; }
    trap restore EXIT

    echo "=== merged ($(git rev-parse --short HEAD)) ==="
    python3 scripts/run_compliance.py --suite test262 --all --log-fail || true
    cp .deps/compliance/logs/test262-latest.json "$work/merged.json"

    for spec in "base:{{base}}" "upstream:upstream/master"; do
        name="${spec%%:*}"; rev="${spec#*:}"
        echo "=== $name ($rev) ==="
        python3 scripts/sync_upstream.py worktree "$work/$name" --rev "$rev"
        meson setup "$work/$name/build" "$work/$name" >/dev/null
        meson compile -C "$work/$name/build"
        cp "$work/$name/build/ant" build/ant
        python3 scripts/run_compliance.py --suite test262 --all --log-fail || true
        cp .deps/compliance/logs/test262-latest.json "$work/$name.json"
    done
    restore

    python3 scripts/sync_upstream.py attribute \
        "$work/base.json" "$work/merged.json" "$work/upstream.json"

# Clean build directory
clean:
    rm -rf build

# Install binary locally
install:
    meson compile -C build
    @if which ant >/dev/null 2>&1; then \
        dir=$$(dirname $$(which ant)); \
        cp ./build/ant "$$dir/ant"; \
        ln -sf "$$dir/ant" "$$dir/antx"; \
    else \
        mkdir -p ~/.ant/bin; \
        cp ./build/ant ~/.ant/bin/; \
        ln -sf ~/.ant/bin/ant ~/.ant/bin/antx; \
    fi
