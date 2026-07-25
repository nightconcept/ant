default: build

# Download subprojects and configure build directory
setup:
    meson subprojects download
    meson setup build --wipe

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

# Build and run a JS file
run file:
    meson compile -C build
    ./build/ant {{file}}

# Run spec tests
test:
    meson compile -C build
    ./build/ant examples/spec/run.js

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
