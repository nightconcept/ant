default: build

# Download subprojects and configure build directory
setup:
    meson subprojects download
    meson setup build --wipe

# Configure build directory without JIT
no_jit:
    meson subprojects download
    meson setup build --wipe -Djit=false

# Configure build directory with AddressSanitizer
asan:
    meson subprojects download
    meson setup build --wipe -Db_sanitize=address -Doptimization=0 -Db_lto=false -Dstrip=false -Db_lundef=false

# Configure build directory for debug
debug:
    meson subprojects download
    meson setup build --wipe --buildtype=debug -Doptimization=0 -Db_lto=false -Dstrip=false -Db_lundef=false -Dunity=off

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
    ant .github/agents/check_all.js

# Check repository knowledge docs
knowledge:
    ant .github/agents/check_repo_knowledge.js

# Check repository structure invariants
structure:
    ant .github/agents/check_repo_structure.js

# Route and report recommended validation for git changes
validate_changes:
    ant .github/agents/route_validation.js

# Run shell environment
shell:
    mise run shell

# Run spec tests
test:
    meson compile -C build
    ./build/ant examples/spec/run.js

# Run benchmark suite
bench +args="":
    meson compile -C build
    python3 bench/bench.py {{args}}

# Run compliance test suite
compliance +args="":
    meson compile -C build
    python3 scripts/run_compliance.py {{args}}


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
