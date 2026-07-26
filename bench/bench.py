#!/usr/bin/env python3
import os
import sys
import json
import shutil
import urllib.request
import tarfile
import zipfile
import subprocess
import platform
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = REPO_ROOT / "bench"
BIN_DIR = BENCH_DIR / "bin"

# Specified versions for external binaries
VERSIONS = {
    "ant_upstream": "v12.2.1d8040ee.1",
    "node": "v22.14.0",
    "bun": "v1.2.2",
    "deno": "v2.2.3",
    "hyperfine": "v1.18.0"
}

def get_platform_info():
    sys_name = platform.system().lower()
    machine = platform.machine().lower()
    
    if sys_name not in ("linux", "darwin"):
        raise RuntimeError(f"Unsupported operating system: {sys_name}")
    
    is_arm = machine in ("aarch64", "arm64")
    return sys_name, is_arm

def download_file(url, target_path):
    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "ant-bench-runner"})
    with urllib.request.urlopen(req) as resp, open(target_path, "wb") as f:
        shutil.copyfileobj(resp, f)

def ensure_binaries():
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    sys_name, is_arm = get_platform_info()

    # Helper map for downloads
    # 1. Upstream Ant
    ant_bin = BIN_DIR / "ant_upstream"
    if not ant_bin.exists():
        ant_tag = VERSIONS["ant_upstream"]
        ant_arch = "aarch64" if is_arm else "x64"
        ant_os = "darwin" if sys_name == "darwin" else "linux"
        ant_url = f"https://github.com/theMackabu/ant/releases/download/{ant_tag}/ant-{ant_os}-{ant_arch}.zip"
        zip_path = BIN_DIR / "ant.zip"
        download_file(ant_url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for item in zf.namelist():
                if item.endswith("ant") or item == "ant":
                    with zf.open(item) as src, open(ant_bin, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    break
        ant_bin.chmod(0o755)
        zip_path.unlink(missing_ok=True)

    # 2. Node.js
    node_bin = BIN_DIR / "node"
    if not node_bin.exists():
        node_ver = VERSIONS["node"]
        node_arch = "arm64" if is_arm else "x64"
        node_os = "darwin" if sys_name == "darwin" else "linux"
        node_ext = "tar.gz" if sys_name == "darwin" else "tar.xz"
        node_url = f"https://nodejs.org/dist/{node_ver}/node-{node_ver}-{node_os}-{node_arch}.{node_ext}"
        archive_path = BIN_DIR / f"node.{node_ext}"
        download_file(node_url, archive_path)
        mode = "r:gz" if node_ext == "tar.gz" else "r:xz"
        with tarfile.open(archive_path, mode) as tf:
            for member in tf.getmembers():
                if member.name.endswith("/bin/node"):
                    extracted = tf.extractfile(member)
                    with open(node_bin, "wb") as dst:
                        shutil.copyfileobj(extracted, dst)
                    break
        node_bin.chmod(0o755)
        archive_path.unlink(missing_ok=True)

    # 3. Bun
    bun_bin = BIN_DIR / "bun"
    if not bun_bin.exists():
        bun_ver = VERSIONS["bun"]
        bun_arch = "aarch64" if is_arm else "x64"
        bun_os = "darwin" if sys_name == "darwin" else "linux"
        bun_url = f"https://github.com/oven-sh/bun/releases/download/bun-{bun_ver}/bun-{bun_os}-{bun_arch}.zip"
        zip_path = BIN_DIR / "bun.zip"
        download_file(bun_url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for item in zf.namelist():
                if item.endswith("/bun") or item == "bun":
                    with zf.open(item) as src, open(bun_bin, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    break
        bun_bin.chmod(0o755)
        zip_path.unlink(missing_ok=True)

    # 4. Deno
    deno_bin = BIN_DIR / "deno"
    if not deno_bin.exists():
        deno_ver = VERSIONS["deno"]
        deno_arch = "aarch64" if is_arm else "x86_64"
        deno_os = "apple-darwin" if sys_name == "darwin" else "unknown-linux-gnu"
        deno_url = f"https://github.com/denoland/deno/releases/download/{deno_ver}/deno-{deno_arch}-{deno_os}.zip"
        zip_path = BIN_DIR / "deno.zip"
        download_file(deno_url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for item in zf.namelist():
                if item.endswith("deno") or item == "deno":
                    with zf.open(item) as src, open(deno_bin, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    break
        deno_bin.chmod(0o755)
        zip_path.unlink(missing_ok=True)

    # 5. Hyperfine
    hyperfine_bin = shutil.which("hyperfine")
    if hyperfine_bin:
        hyperfine_path = Path(hyperfine_bin)
    else:
        hyperfine_path = BIN_DIR / "hyperfine"
        if not hyperfine_path.exists():
            hf_ver = VERSIONS["hyperfine"]
            hf_arch = "aarch64" if is_arm else "x86_64"
            hf_os = "apple-darwin" if sys_name == "darwin" else "unknown-linux-gnu"
            hf_url = f"https://github.com/sharkdp/hyperfine/releases/download/{hf_ver}/hyperfine-{hf_ver}-{hf_arch}-{hf_os}.tar.gz"
            archive_path = BIN_DIR / "hyperfine.tar.gz"
            download_file(hf_url, archive_path)
            with tarfile.open(archive_path, "r:gz") as tf:
                for member in tf.getmembers():
                    if member.name.endswith("/hyperfine") or member.name == "hyperfine":
                        extracted = tf.extractfile(member)
                        with open(hyperfine_path, "wb") as dst:
                            shutil.copyfileobj(extracted, dst)
                        break
            hyperfine_path.chmod(0o755)
            archive_path.unlink(missing_ok=True)

    return {
        "ant_fork": REPO_ROOT / "build" / "ant",
        "ant_upstream": ant_bin,
        "node": node_bin,
        "bun": bun_bin,
        "deno": deno_bin,
        "hyperfine": hyperfine_path
    }

def get_file_size_mb(path):
    if not path.exists():
        return "N/A"
    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return f"~{size_mb:.1f} MB"

def run_benchmarks(bins, warmup=10, runs=100):
    script_path = REPO_ROOT / "examples" / "npm" / "hono" / "bench-coldstart.js"
    if not script_path.exists():
        raise RuntimeError(f"Benchmark script not found at {script_path}")

    hono_dir = script_path.parent
    node_modules_dir = hono_dir / "node_modules"
    if not node_modules_dir.exists():
        print("Installing dependencies in examples/npm/hono...")
        subprocess.run(["npm", "install"], check=True, cwd=hono_dir)

    # Build commands
    commands = {
        "Ant (Fork)": f"'{bins['ant_fork']} {script_path}'",
        "Ant (Upstream)": f"'{bins['ant_upstream']} {script_path}'",
        "Bun": f"'{bins['bun']} {script_path}'",
        "Deno": f"'{bins['deno']} run --allow-read --allow-env {script_path}'",
        "Node": f"'{bins['node']} {script_path}'",
    }

    hyperfine_cmd = [
        str(bins["hyperfine"]),
        "--warmup", str(warmup),
        "--runs", str(runs),
        "--export-json", str(BENCH_DIR / "results.json")
    ]
    for label, cmd_str in commands.items():
        hyperfine_cmd.extend(["-n", label, cmd_str.strip("'")])

    print("\nRunning cold-start benchmark using hyperfine...")
    subprocess.run(hyperfine_cmd, check=True, cwd=REPO_ROOT)

    # Read hyperfine JSON results
    with open(BENCH_DIR / "results.json", "r") as f:
        results_data = json.load(f)

    return results_data

def format_output(bins, results_data, check_thresholds=False, max_speed_lag=10.0, max_size_growth=25.0):
    fork_bin = bins["ant_fork"]
    upstream_bin = bins["ant_upstream"]

    # Map binary sizes
    fork_size = get_file_size_mb(fork_bin)
    upstream_size = get_file_size_mb(upstream_bin)
    node_size = get_file_size_mb(bins["node"])
    bun_size = get_file_size_mb(bins["bun"])
    deno_size = get_file_size_mb(bins["deno"])

    # 1. Overview Table
    overview_table = []
    overview_table.append("| Runtime | Engine | JIT | WinterTC | Binary size |")
    overview_table.append("| ------- | ------ | --- | -------- | ----------- |")
    overview_table.append(f"| **Ant (Fork)** | Ant Silver | ✓ | ✓ | **{fork_size}** |")
    overview_table.append(f"| Ant (Upstream {VERSIONS['ant_upstream']}) | Ant Silver | ✓ | ✓ | {upstream_size} |")
    overview_table.append(f"| Node ({VERSIONS['node']}) | V8 | ✓ | partial | {node_size} |")
    overview_table.append(f"| Bun ({VERSIONS['bun']}) | JSC | ✓ | ✓ | {bun_size} |")
    overview_table.append(f"| Deno ({VERSIONS['deno']}) | V8 | ✓ | ✓ | {deno_size} |")

    # 2. Cold Start Table
    runs = results_data.get("results", [])
    fastest_mean = min(r["mean"] for r in runs) if runs else 1.0

    coldstart_table = []
    coldstart_table.append("| Runtime | Mean | Min | Max | Relative |")
    coldstart_table.append("| ------- | ---- | --- | --- | -------- |")

    fork_mean = None
    upstream_mean = None

    for r in sorted(runs, key=lambda x: x["mean"]):
        name = r["command"] # set by -n
        mean_ms = r["mean"] * 1000
        min_ms = r["min"] * 1000
        max_ms = r["max"] * 1000
        rel = r["mean"] / fastest_mean

        if name == "Ant (Fork)":
            fork_mean = r["mean"]
        elif name == "Ant (Upstream)":
            upstream_mean = r["mean"]

        rel_str = "**1.00**" if rel == 1.0 else f"{rel:.2f}× slower"
        name_str = f"**{name}**" if rel == 1.0 else name

        coldstart_table.append(
            f"| {name_str} | {mean_ms:.1f} ms | {min_ms:.1f} ms | {max_ms:.1f} ms | {rel_str} |"
        )

    print("\n" + "=" * 60)
    print("### Feature & Size Comparison")
    print("\n".join(overview_table))
    print("\n### Cold Start Benchmark (Hono import & route registration)")
    print("\n".join(coldstart_table))
    print("=" * 60 + "\n")

    # 3. Threshold Checks against Upstream Ant
    threshold_passed = True
    threshold_summary = []

    if fork_bin.exists() and upstream_bin.exists():
        fork_bytes = fork_bin.stat().st_size
        upstream_bytes = upstream_bin.stat().st_size
        size_growth_pct = ((fork_bytes - upstream_bytes) / upstream_bytes) * 100.0

        size_ok = size_growth_pct <= max_size_growth
        if not size_ok:
            threshold_passed = False

        size_status = "PASS" if size_ok else "FAIL"
        size_msg = (
            f"Binary Size: Fork ({fork_bytes / (1024*1024):.2f} MB) vs Upstream ({upstream_bytes / (1024*1024):.2f} MB) "
            f"-> {size_growth_pct:+.1f}% (Limit: +{max_size_growth:.1f}%) [{size_status}]"
        )
        print(size_msg)

        threshold_summary.append("| Metric | Upstream | Fork | Diff | Max Limit | Status |")
        threshold_summary.append("| ------ | -------- | ---- | ---- | --------- | ------ |")
        threshold_summary.append(
            f"| Binary Size | {upstream_bytes / (1024*1024):.2f} MB | {fork_bytes / (1024*1024):.2f} MB | "
            f"{size_growth_pct:+.1f}% | +{max_size_growth:.1f}% | **{size_status}** |"
        )

        if fork_mean is not None and upstream_mean is not None:
            speed_lag_pct = ((fork_mean - upstream_mean) / upstream_mean) * 100.0
            speed_ok = speed_lag_pct <= max_speed_lag
            if not speed_ok:
                threshold_passed = False

            speed_status = "PASS" if speed_ok else "FAIL"
            speed_msg = (
                f"Cold Start Speed: Fork ({fork_mean*1000:.1f} ms) vs Upstream ({upstream_mean*1000:.1f} ms) "
                f"-> {speed_lag_pct:+.1f}% (Limit: +{max_speed_lag:.1f}% slower) [{speed_status}]"
            )
            print(speed_msg)

            threshold_summary.append(
                f"| Cold Start Speed | {upstream_mean*1000:.1f} ms | {fork_mean*1000:.1f} ms | "
                f"{speed_lag_pct:+.1f}% | +{max_speed_lag:.1f}% | **{speed_status}** |"
            )

    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            with open(gh_summary, "a", encoding="utf-8") as f:
                f.write("### Cold-Start Benchmark & Threshold Results\n\n")
                f.write("#### Feature & Size Comparison\n\n")
                f.write("\n".join(overview_table) + "\n\n")
                f.write("#### Cold Start Benchmark (Hono import & route registration)\n\n")
                f.write("\n".join(coldstart_table) + "\n\n")
                if threshold_summary:
                    f.write("#### Performance & Size Threshold Assertions vs Upstream Ant\n\n")
                    f.write("\n".join(threshold_summary) + "\n\n")
        except Exception:
            pass

    if check_thresholds and not threshold_passed:
        print("\nERROR: Performance or size threshold assertion failed against Upstream Ant!")
        return False

    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ant Cold-Start Benchmark & Threshold Runner")
    parser.add_argument("--warmup", type=int, default=10, help="Hyperfine warmup iterations (default: 10)")
    parser.add_argument("--runs", type=int, default=100, help="Hyperfine benchmark iterations (default: 100)")
    parser.add_argument("--check-thresholds", action="store_true", help="Assert performance and size thresholds against Upstream Ant")
    parser.add_argument("--max-speed-lag", type=float, default=10.0, help="Maximum allowed speed lag vs Upstream Ant in % (default: 10.0)")
    parser.add_argument("--max-size-growth", type=float, default=25.0, help="Maximum allowed binary size growth vs Upstream Ant in % (default: 25.0)")
    args = parser.parse_args()

    print("Ensuring benchmark runtimes and tools exist...")
    bins = ensure_binaries()
    results = run_benchmarks(bins, warmup=args.warmup, runs=args.runs)
    passed = format_output(
        bins,
        results,
        check_thresholds=args.check_thresholds,
        max_speed_lag=args.max_speed_lag,
        max_size_growth=args.max_size_growth
    )
    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
