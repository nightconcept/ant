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

def format_output(bins, results_data):
    # Map binary sizes
    fork_size = get_file_size_mb(bins["ant_fork"])
    upstream_size = get_file_size_mb(bins["ant_upstream"])
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
    # Sort or parse hyperfine output
    runs = results_data.get("results", [])
    # Find baseline (fastest mean)
    fastest_mean = min(r["mean"] for r in runs) if runs else 1.0

    coldstart_table = []
    coldstart_table.append("| Runtime | Mean | Min | Max | Relative |")
    coldstart_table.append("| ------- | ---- | --- | --- | -------- |")

    for r in sorted(runs, key=lambda x: x["mean"]):
        name = r["command"] # set by -n
        mean_ms = r["mean"] * 1000
        min_ms = r["min"] * 1000
        max_ms = r["max"] * 1000
        rel = r["mean"] / fastest_mean

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

def main():
    print("Ensuring benchmark runtimes and tools exist...")
    bins = ensure_binaries()
    results = run_benchmarks(bins)
    format_output(bins, results)

if __name__ == "__main__":
    main()
