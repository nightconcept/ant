#!/usr/bin/env python3
import os
import sys
import re
import json
import stat
import shutil
import platform
import zipfile
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
BIN_DIR = ROOT_DIR / "bin"
BENCH_DIR = ROOT_DIR / "benchmarks"
MANIFEST_PATH = ROOT_DIR / "versions.json"

BENCHMARKS = [
    # tier "fast" entries run in `--fast`; everything runs in the full suite.
    # "runtimes" restricts a benchmark to a subset (used by the Ant-only group,
    # where no portable cross-runtime API exists).
    {
        "id": "fib",
        "name": "Fibonacci Recursion",
        "desc": "Recursive computation fib(36) - CPU & recursion overhead",
        # Full tier only: txiki.js takes ~1.2s here, four times Ant, making this
        # the most expensive entry in the fast tier by a wide margin. Call and
        # dispatch overhead is still covered per-iteration by richards and
        # class_dispatch, on more realistic code than bare recursion.
        "tier": "full",
        "ts": "fib.ts",
        "js": "fib.js"
    },
    {
        "id": "json",
        "name": "JSON Serialization",
        "desc": "40 iterations of stringifying & parsing 5,000 objects",
        "tier": "fast",
        "ts": "json.ts",
        "js": "json.js"
    },
    {
        "id": "string",
        "name": "String Manipulations",
        "desc": "Case, split, join & slice over a 220KB string (50 passes)",
        "tier": "fast",
        "ts": "string.ts",
        "js": "string.js"
    },
    {
        "id": "array",
        "name": "Array Operations",
        "desc": "Filter, map, sort & reduce on 100k items (10 passes)",
        "tier": "fast",
        "ts": "array.ts",
        "js": "array.js"
    },
    {
        "id": "async",
        "name": "Async & Microtasks",
        "desc": "2,000 concurrent async promise chains (100 steps each)",
        "tier": "fast",
        "ts": "async.ts",
        "js": "async.js"
    },
    {
        "id": "coldstart",
        "name": "Cold Start (Hono App)",
        "desc": "Import Hono router, register routes & exit - module init overhead",
        "tier": "fast",
        "ts": "coldstart.js",
        "js": "coldstart.js"
    },
    {
        "id": "object_graph",
        "name": "Object Graph & AST",
        "desc": "150k AST object nodes creation, linking & traversal - heap & GC overhead",
        "tier": "fast",
        "ts": "object_graph.ts",
        "js": "object_graph.js"
    },
    {
        "id": "string_rope",
        "name": "Rope String Concatenation",
        "desc": "500k high-frequency string concatenations, slicing & indexOf search",
        "tier": "fast",
        "ts": "string_rope.ts",
        "js": "string_rope.js"
    },
    {
        "id": "map_set",
        "name": "Map & Set Collections",
        "desc": "Insert, lookup, delete & iterate over Map/Set (20k keys, 9 passes)",
        "tier": "fast",
        "ts": "map_set.ts",
        "js": "map_set.js"
    },
    {
        "id": "class_dispatch",
        "name": "Class & Megamorphic Dispatch",
        "desc": "super chains, accessors & 4-shape megamorphic call sites (14 passes)",
        "tier": "fast",
        "ts": "class_dispatch.ts",
        "js": "class_dispatch.js"
    },
    {
        "id": "exceptions",
        "name": "Exception Unwinding",
        "desc": "15k throw/catch cycles across call depth, with stack capture",
        "tier": "fast",
        "ts": "exceptions.ts",
        "js": "exceptions.js"
    },
    {
        "id": "gc_pressure",
        "name": "GC Pressure & Promotion",
        "desc": "40k long-lived objects churned against 20k short-lived per pass",
        "tier": "fast",
        "ts": "gc_pressure.ts",
        "js": "gc_pressure.js"
    },
    {
        "id": "stream_pipe",
        "name": "Web Streams Pipeline",
        "desc": "ReadableStream -> 2x TransformStream -> reader (16 rounds x 200 chunks)",
        "tier": "fast",
        "ts": "stream_pipe.ts",
        "js": "stream_pipe.js"
    },
    {
        "id": "richards",
        "name": "Richards OS Simulation",
        "desc": "OS task queue simulation - OOP method dispatch & state machine",
        "tier": "fast",
        "ts": "richards.ts",
        "js": "richards.js"
    },
    {
        "id": "solo_http",
        "name": "HTTP Server Round-Trip",
        "desc": "1,800 in-process fetch round-trips against Ant.serve (Ant only)",
        "tier": "fast",
        "runtimes": ["ant"],
        "ts": "solo_http.js",
        "js": "solo_http.js"
    },
    {
        "id": "solo_fs",
        "name": "Filesystem Churn",
        "desc": "write/stat/read/append/rename/unlink over 600 files x 8 passes (Ant only)",
        "tier": "fast",
        "runtimes": ["ant"],
        "ts": "solo_fs.js",
        "js": "solo_fs.js"
    },
    {
        "id": "closures",
        "name": "Closures & Upvalues",
        "desc": "Escaping closures, shared captures & deep composition (3,000 passes)",
        "tier": "full",
        "ts": "closures.ts",
        "js": "closures.js"
    },
    {
        "id": "proxy_trap",
        "name": "Proxy Trap Interception",
        "desc": "200k property get/set intercept traps via ES6 Proxy handler",
        "tier": "full",
        "ts": "proxy_trap.ts",
        "js": "proxy_trap.js"
    },
    {
        "id": "text_codec",
        "name": "TextEncoder/Decoder UTF-8",
        "desc": "300 iterations of UTF-8 encoding/decoding multi-MB Unicode strings",
        "tier": "full",
        "ts": "text_codec.ts",
        "js": "text_codec.js"
    },
    {
        "id": "nbody",
        "name": "N-Body Simulation",
        "desc": "3D celestial physics simulation (75k steps) - float math & loops",
        "tier": "full",
        "ts": "nbody.ts",
        "js": "nbody.js"
    },
    {
        "id": "fannkuch",
        "name": "Fannkuch-Redux",
        "desc": "Indexed array permutation & flip reversal (N=9)",
        "tier": "full",
        "ts": "fannkuch.ts",
        "js": "fannkuch.js"
    },
    {
        "id": "spectral_norm",
        "name": "Spectral Norm",
        "desc": "Eigenvalue spectral norm matrix calculation (N=500)",
        "tier": "full",
        "ts": "spectral_norm.ts",
        "js": "spectral_norm.js"
    },
    {
        "id": "deltablue",
        "name": "DeltaBlue Constraint Solver",
        "desc": "Constraint graph solver - dynamic type checks & graph mutation",
        "tier": "full",
        "ts": "deltablue.ts",
        "js": "deltablue.js"
    },
    {
        "id": "heapsort",
        "name": "HeapSort Array Sort",
        "desc": "In-place HeapSort over 150k elements - non-sequential memory swaps",
        "tier": "full",
        "ts": "heapsort.ts",
        "js": "heapsort.js"
    },
    {
        "id": "generators",
        "name": "Generators & Iterators",
        "desc": "7k delegating generator invocations (yield*) & iteration protocol",
        "tier": "full",
        "ts": "generators.ts",
        "js": "generators.js"
    },
    {
        "id": "regex_dna",
        "name": "Regex DNA Processing",
        "desc": "DNA sequence pattern matching, capturing & IUPAC replacements",
        "tier": "full",
        "ts": "regex_dna.ts",
        "js": "regex_dna.js"
    }
]

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# "fast" runtimes are the ones `--fast` keeps: Ant, the reference (node) that
# the ratio in scripts/bench_baseline.py divides machine noise out against, and
# txiki.js as the closest-peer small runtime. Deno and Bun are full-suite only.
RUNTIMES = [
    {
        "id": "ant",
        "name": "ant",
        "repo": "themackabu/ant",
        "color": GREEN,
        "ts_file": True,
        "fast": True,
        "args": []
    },
    {
        "id": "tjs",
        "name": "txiki.js",
        "repo": "saghul/txiki.js",
        "color": YELLOW,
        "ts_file": False,
        "fast": True,
        "args": ["run"]
    },
    {
        "id": "node",
        "name": "Node.js",
        "repo": "nodejs/node",
        "color": BLUE,
        "ts_file": False,
        "fast": True,
        "args": []
    },
    {
        "id": "deno",
        "name": "Deno",
        "repo": "denoland/deno",
        "color": MAGENTA,
        "ts_file": True,
        "fast": False,
        # --allow-env so a benchmark reading process.env does not die on a
        # permission prompt; Deno throws where the other four return undefined.
        "args": ["run", "--allow-env"]
    },
    {
        "id": "bun",
        "name": "Bun",
        "repo": "oven-sh/bun",
        "color": CYAN,
        "ts_file": True,
        "fast": False,
        "args": ["run"]
    }
]

# Wall-clock ceiling for a single benchmark's hyperfine invocation. A hung
# benchmark used to block the suite forever - fannkuch did exactly that, on
# every runtime at once - because hyperfine has no timeout of its own.
HYPERFINE_TIMEOUT_S = 300

# Sampling, shared by both tiers.
#
# Benchmark noise is one-sided: scheduling, interrupts, cache eviction and
# thermal effects can only make a sample slower, never faster than the machine
# is capable of. So the fastest sample is the cleanest estimate of the real
# cost, and the mean is an estimate of "cost plus whatever else the machine was
# doing". Measured over 8 independent invocations of 6 benchmarks, drift
# between invocations of identical code:
#
#   estimator      runs   median   p90    max
#   mean             10     1.8%   3.9%   6.9%
#   mean              6     2.6%   5.7%   8.2%
#   trim-2-slowest    6     2.2%   3.8%   7.1%
#   min               5     1.5%   3.1%   3.9%
#   min              10     0.8%   1.4%   3.7%
#
# min at 5 runs is more stable than the mean at 10 while taking half the
# samples, which is what lets both tiers get faster and gate tighter at once.
WARMUP_RUNS = 1
TIMED_RUNS = 5

# Field of the hyperfine result used for gating and for the work column.
BEST_METRIC = "min"

def strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

def pad_cell(text: str, width: int, align="left") -> str:
    visible_len = len(strip_ansi(text))
    padding = max(0, width - visible_len)
    if align == "right":
        return " " * padding + text
    elif align == "center":
        left = padding // 2
        right = padding - left
        return " " * left + text + " " * right
    return text + " " * padding

def get_platform_info():
    system = platform.system().lower()
    machine = platform.machine().lower()
    is_mac = system == "darwin"
    is_linux = system == "linux"
    is_arm = machine in ("arm64", "aarch64")
    return system, machine, is_mac, is_linux, is_arm

def resolve_binary(name: str) -> Path:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r") as f:
                vdata = json.load(f)
                r_info = vdata.get("runtimes", {}).get(name, {})
                vp = r_info.get("binary_path")
                if vp:
                    p = Path(vp)
                    if p.is_absolute() and p.exists() and p.is_file():
                        return p
                    rel_p = ROOT_DIR / p
                    if rel_p.exists() and rel_p.is_file():
                        return rel_p
                    parent_p = ROOT_DIR.parent / p
                    if parent_p.exists() and parent_p.is_file():
                        return parent_p
        except Exception:
            pass

    local_bin = BIN_DIR / name
    if local_bin.exists() and local_bin.is_file():
        return local_bin
    local_bin_exe = BIN_DIR / f"{name}.exe"
    if local_bin_exe.exists() and local_bin_exe.is_file():
        return local_bin_exe

    build_bin = ROOT_DIR.parent / "build" / name
    if build_bin.exists() and build_bin.is_file():
        return build_bin

    which_path = shutil.which(name)
    if which_path:
        return Path(which_path)

    if shutil.which("mise"):
        try:
            res = subprocess.run(["mise", "which", name], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                p = Path(res.stdout.strip())
                if p.exists():
                    return p
        except Exception:
            pass

    return local_bin

def fetch_latest_release_asset(repo: str, asset_name_exact: str = "", asset_substr: str = ""):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Python/3.13)"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        tag = data.get("tag_name", "latest")
        if asset_name_exact:
            for asset in data.get("assets", []):
                if asset["name"] == asset_name_exact:
                    return tag, asset["name"], asset["browser_download_url"]
        if asset_substr:
            for asset in data.get("assets", []):
                name = asset["name"]
                if asset_substr in name and not name.endswith(".bsdiff") and "profile" not in name and "baseline" not in name:
                    return tag, name, asset["browser_download_url"]
    raise RuntimeError(f"No asset matching '{asset_name_exact or asset_substr}' found in {repo} releases")

def ensure_binaries(force_update=False):
    BIN_DIR.mkdir(exist_ok=True)
    bin_map = {}
    asset_info = {}
    system, machine, is_mac, is_linux, is_arm = get_platform_info()

    for r in RUNTIMES:
        r_id = r["id"]
        bin_path = resolve_binary(r_id)

        if r_id == "ant":
            build_bin = ROOT_DIR.parent / "build" / "ant"
            if build_bin.exists() and build_bin.is_file() and build_bin.stat().st_size > 0:
                target = BIN_DIR / "ant"
                try:
                    shutil.copy2(build_bin, target)
                    target.chmod(target.stat().st_mode | stat.S_IEXEC)
                except Exception:
                    pass
                bin_map["ant"] = target
                continue

        if not force_update and bin_path.exists() and bin_path.is_file():
            bin_map[r_id] = bin_path
            continue

        if r_id == "ant":
            ant_pattern = "ant-darwin-aarch64" if (is_mac and is_arm) else \
                          "ant-darwin-x64" if is_mac else \
                          "ant-linux-aarch64" if (is_linux and is_arm) else "ant-linux-x64"
            try:
                tag, name, download_url = fetch_latest_release_asset("themackabu/ant", asset_substr=ant_pattern)
                print(f"  ➜ Downloading ant {tag} ({name})...", flush=True)
                ant_zip = BIN_DIR / "ant.zip"
                urllib.request.urlretrieve(download_url, ant_zip)
                with zipfile.ZipFile(ant_zip, 'r') as zip_ref:
                    zip_ref.extractall(BIN_DIR)
                ant_zip.unlink(missing_ok=True)
                target = BIN_DIR / "ant"
                target.chmod(target.stat().st_mode | stat.S_IEXEC)
                bin_map["ant"] = target
                asset_info["ant"] = {"tag": tag, "url": download_url, "asset": name}
            except Exception as e:
                print(f"⚠️ Failed to fetch ant release: {e}", flush=True)
                bin_map["ant"] = bin_path

        elif r_id == "tjs":
            txiki_pattern = "txiki-macos-arm64" if (is_mac and is_arm) else \
                            "txiki-macos-x86_64" if is_mac else \
                            "txiki-linux-x86_64" if is_linux else "txiki-windows"
            try:
                tag, name, download_url = fetch_latest_release_asset("saghul/txiki.js", asset_substr=txiki_pattern)
                print(f"  ➜ Downloading txiki.js {tag} ({name})...", flush=True)
                txiki_zip = BIN_DIR / "txiki.zip"
                urllib.request.urlretrieve(download_url, txiki_zip)
                with zipfile.ZipFile(txiki_zip, 'r') as zip_ref:
                    zip_ref.extractall(BIN_DIR)
                txiki_zip.unlink(missing_ok=True)
                target = BIN_DIR / "tjs"
                for p in BIN_DIR.rglob("tjs"):
                    if p.is_file() and p != target:
                        shutil.copy2(p, target)
                        break
                target.chmod(target.stat().st_mode | stat.S_IEXEC)
                bin_map["tjs"] = target
                asset_info["tjs"] = {"tag": tag, "url": download_url, "asset": name}
            except Exception as e:
                print(f"  ➜ Release asset unavailable ({e}). Building txiki.js from source...", flush=True)
                try:
                    tmp_dir = BIN_DIR / ".tmp_tjs"
                    if tmp_dir.exists():
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                    subprocess.run(["git", "clone", "--depth", "1", "https://github.com/saghul/txiki.js.git", str(tmp_dir)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["git", "submodule", "update", "--init", "--recursive", "--depth", "1"], cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["cmake", "-B", "build"], cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["cmake", "--build", "build", "-j"], cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    target = BIN_DIR / "tjs"
                    shutil.copy2(tmp_dir / "build" / "tjs", target)
                    target.chmod(target.stat().st_mode | stat.S_IEXEC)
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    bin_map["tjs"] = target
                    asset_info["tjs"] = {"tag": "source-build", "url": "https://github.com/saghul/txiki.js", "asset": "source"}
                    print("  ✓ Built txiki.js successfully", flush=True)
                except Exception as build_err:
                    print(f"⚠️ Failed to build txiki.js from source: {build_err}", flush=True)
                    bin_map["tjs"] = bin_path

        elif r_id == "bun":
            bun_exact = "bun-darwin-aarch64.zip" if (is_mac and is_arm) else \
                        "bun-darwin-x64.zip" if is_mac else \
                        "bun-linux-aarch64.zip" if (is_linux and is_arm) else "bun-linux-x64.zip"
            try:
                tag, name, download_url = fetch_latest_release_asset("oven-sh/bun", asset_name_exact=bun_exact, asset_substr=bun_exact.replace(".zip", ""))
                print(f"  ➜ Downloading Bun {tag} ({name})...", flush=True)
                bun_zip = BIN_DIR / "bun.zip"
                urllib.request.urlretrieve(download_url, bun_zip)
                with zipfile.ZipFile(bun_zip, 'r') as zip_ref:
                    zip_ref.extractall(BIN_DIR)
                bun_zip.unlink(missing_ok=True)
                target = BIN_DIR / "bun"
                for p in BIN_DIR.rglob("bun"):
                    if p.is_file() and p != target:
                        shutil.copy2(p, target)
                        break
                target.chmod(target.stat().st_mode | stat.S_IEXEC)
                bin_map["bun"] = target
                asset_info["bun"] = {"tag": tag, "url": download_url, "asset": name}
            except Exception as e:
                print(f"⚠️ Failed to fetch Bun release: {e}", flush=True)
                bin_map["bun"] = bin_path

        elif r_id == "deno":
            deno_exact = "deno-aarch64-apple-darwin.zip" if (is_mac and is_arm) else \
                         "deno-x86_64-apple-darwin.zip" if is_mac else \
                         "deno-aarch64-unknown-linux-gnu.zip" if (is_linux and is_arm) else "deno-x86_64-unknown-linux-gnu.zip"
            try:
                tag, name, download_url = fetch_latest_release_asset("denoland/deno", asset_name_exact=deno_exact, asset_substr=deno_exact.replace(".zip", ""))
                print(f"  ➜ Downloading Deno {tag} ({name})...", flush=True)
                deno_zip = BIN_DIR / "deno.zip"
                urllib.request.urlretrieve(download_url, deno_zip)
                with zipfile.ZipFile(deno_zip, 'r') as zip_ref:
                    zip_ref.extractall(BIN_DIR)
                deno_zip.unlink(missing_ok=True)
                target = BIN_DIR / "deno"
                for p in BIN_DIR.rglob("deno"):
                    if p.is_file() and p != target:
                        shutil.copy2(p, target)
                        break
                target.chmod(target.stat().st_mode | stat.S_IEXEC)
                bin_map["deno"] = target
                asset_info["deno"] = {"tag": tag, "url": download_url, "asset": name}
            except Exception as e:
                print(f"⚠️ Failed to fetch Deno release: {e}", flush=True)
                bin_map["deno"] = bin_path

        elif r_id == "node":
            try:
                if shutil.which("mise"):
                    print("  ➜ Installing Node.js via mise...", flush=True)
                    subprocess.run(["mise", "install", "node@latest"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    node_p = resolve_binary("node")
                    if node_p.exists() and node_p.is_file():
                        bin_map["node"] = node_p
                        asset_info["node"] = {"tag": "latest", "url": "https://nodejs.org", "asset": "mise"}
                        continue

                node_arch = "arm64" if is_arm else "x64"
                node_os = "darwin" if is_mac else "linux"
                node_url = "https://nodejs.org/dist/index.json"
                req = urllib.request.Request(node_url, headers={"User-Agent": "Mozilla/5.0 (Python/3.13)"})
                with urllib.request.urlopen(req) as resp:
                    n_data = json.loads(resp.read().decode())
                    latest_node = n_data[0]["version"]
                tar_name = f"node-{latest_node}-{node_os}-{node_arch}.tar.gz"
                dl_url = f"https://nodejs.org/dist/{latest_node}/{tar_name}"
                print(f"  ➜ Downloading Node.js {latest_node} ({tar_name})...", flush=True)
                node_tar = BIN_DIR / "node.tar.gz"
                urllib.request.urlretrieve(dl_url, node_tar)
                import tarfile
                with tarfile.open(node_tar, "r:gz") as tar_ref:
                    tar_ref.extractall(BIN_DIR)
                node_tar.unlink(missing_ok=True)
                extracted_dir = BIN_DIR / f"node-{latest_node}-{node_os}-{node_arch}"
                extracted_node = extracted_dir / "bin" / "node"
                target = BIN_DIR / "node"
                if extracted_node.exists():
                    shutil.copy2(extracted_node, target)
                    target.chmod(target.stat().st_mode | stat.S_IEXEC)
                    shutil.rmtree(extracted_dir, ignore_errors=True)
                    bin_map["node"] = target
                    asset_info["node"] = {"tag": latest_node, "url": dl_url, "asset": tar_name}
                else:
                    bin_map["node"] = bin_path
            except Exception as e:
                print(f"⚠️ Failed to fetch Node.js release: {e}", flush=True)
                bin_map["node"] = bin_path

        else:
            bin_map[r_id] = bin_path

    return bin_map, asset_info

def get_runtime_version(bin_path: Path, r_id: str) -> str:
    try:
        if r_id == "ant":
            proc = subprocess.run([str(bin_path), "-v"], capture_output=True, text=True, timeout=3)
            lines = (proc.stdout + proc.stderr).splitlines()
            for line in lines:
                line = strip_ansi(line.strip())
                if line and ("released" in line or re.match(r"^\d+\.\d+", line)):
                    ver = line.split()[0]
                    return f"v{ver}" if not ver.startswith("v") else ver
        elif r_id == "tjs":
            proc = subprocess.run([str(bin_path), "-v"], capture_output=True, text=True, timeout=3)
            ver = strip_ansi((proc.stdout or proc.stderr).strip().splitlines()[0])
            return ver
        elif r_id == "node":
            proc = subprocess.run([str(bin_path), "-v"], capture_output=True, text=True, timeout=3)
            ver = strip_ansi((proc.stdout or proc.stderr).strip().splitlines()[0])
            return ver
        elif r_id == "deno":
            proc = subprocess.run([str(bin_path), "--version"], capture_output=True, text=True, timeout=3)
            first_line = strip_ansi((proc.stdout or proc.stderr).splitlines()[0].strip())
            match = re.search(r"deno\s+(\d+\.\d+\.\d+)", first_line)
            if match:
                return f"v{match.group(1)}"
            return first_line
        elif r_id == "bun":
            proc = subprocess.run([str(bin_path), "-v"], capture_output=True, text=True, timeout=3)
            ver = strip_ansi((proc.stdout or proc.stderr).strip().splitlines()[0])
            return f"v{ver}" if not ver.startswith("v") else ver
    except Exception:
        pass
    return "unknown"

def update_version_manifest(bin_map: dict, versions: dict, asset_info: dict):
    manifest_data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "runtimes": {}
    }

    for r in RUNTIMES:
        r_id = r["id"]
        b_path = bin_map.get(r_id, Path(r_id))
        info = asset_info.get(r_id, {})
        size_mb = b_path.stat().st_size / (1024 * 1024) if b_path.exists() else 0.0
        manifest_data["runtimes"][r_id] = {
            "name": r["name"],
            "repo": r["repo"],
            "version": versions.get(r_id, "unknown"),
            "binary_path": str(b_path.relative_to(ROOT_DIR)) if b_path.is_relative_to(ROOT_DIR) else str(b_path),
            "binary_size_mb": round(size_mb, 2),
            "download_url": info.get("url", f"https://github.com/{r['repo']}/releases/latest"),
            "asset_name": info.get("asset", "N/A"),
            "ts_native": r["ts_file"]
        }

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest_data, f, indent=2)

def ensure_js_bundles(tjs_bin: Path):
    if not tjs_bin or not tjs_bin.exists():
        return
    for bench in BENCHMARKS:
        ts_path = BENCH_DIR / bench["ts"]
        js_path = BENCH_DIR / bench["js"]
        if ts_path.exists() and not js_path.exists():
            cmd = [str(tjs_bin), "bundle", str(ts_path), str(js_path)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def measure_peak_rss(cmd: list) -> float:
    system = platform.system().lower()
    if system == "darwin":
        try:
            proc = subprocess.run(["/usr/bin/time", "-l"] + cmd, capture_output=True, text=True)
            match = re.search(r'(\d+)\s+maximum resident set size', proc.stderr)
            if match:
                return int(match.group(1)) / (1024 * 1024)
        except Exception:
            pass
    elif system == "linux":
        try:
            proc = subprocess.run(["/usr/bin/time", "-v"] + cmd, capture_output=True, text=True)
            match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', proc.stderr)
            if match:
                return int(match.group(1)) / 1024
        except Exception:
            pass
    return 0.0

def measure_startup_floor(bin_map: dict, runtimes: list, samples: int = 12) -> dict:
    """Median wall time for each runtime to start and exit on a trivial script.

    Every benchmark's wall time includes this constant. Without subtracting it,
    a benchmark whose real work is a few milliseconds reports mostly process
    startup: measured floors run from ~4ms (Ant) to ~18ms (node), so a 3ms
    workload was being published as a compute ratio when it was a startup
    ratio. Reported separately as a metric in its own right, too - Ant starting
    in a quarter of node's time is a genuine result.
    """
    # Written into BENCH_DIR, not the bench root: module resolution walks the
    # directory tree, so a floor measured elsewhere would not match what the
    # real benchmarks pay.
    probe = BENCH_DIR / "temp_startup_probe.js"
    probe.write_text("const x = 1;\n")
    floors = {}
    try:
        for r in runtimes:
            bin_p = bin_map.get(r["id"])
            if not bin_p or not Path(bin_p).exists():
                continue
            cmd = [str(bin_p)] + r["args"] + [str(probe)]

            # Liveness check, bounded. The timed samples below deliberately run
            # without a timeout: subprocess.run(timeout=...) makes Popen.wait
            # poll with exponential backoff (0.5ms doubling to 50ms), which
            # roughly doubles the measured time for a process this short - node
            # reads 32ms timed against 16ms untimed. One bounded run proves the
            # runtime exits; after that, accuracy wins.
            try:
                if subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=30).returncode != 0:
                    continue
            except (subprocess.TimeoutExpired, OSError):
                continue

            times = []
            for _ in range(samples):
                t0 = time.perf_counter()
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                except OSError:
                    times = []
                    break
                times.append((time.perf_counter() - t0) * 1000.0)
            if times:
                times.sort()
                floors[r["id"]] = times[len(times) // 2]
    finally:
        probe.unlink(missing_ok=True)
    return floors

def get_hyperfine_base_cmd():
    local_hf = BIN_DIR / "hyperfine"
    if local_hf.exists() and local_hf.is_file():
        return [str(local_hf)]
    if shutil.which("hyperfine"):
        return [shutil.which("hyperfine")]
    if shutil.which("mise"):
        return ["mise", "exec", "--", "hyperfine"]
    home = Path.home()
    mise_installs = list(home.glob(".local/share/mise/installs/hyperfine/**/hyperfine"))
    if mise_installs:
        return [str(mise_installs[0])]
    return ["hyperfine"]

def run_hyperfine(cmds_map: dict, warmup: int = 2, runs: int = 10) -> dict:
    temp_json = ROOT_DIR / "temp_hyperfine.json"
    r_order = list(cmds_map.keys())
    cmd_strs = [" ".join(str(c) for c in cmds_map[r_id]) for r_id in r_order]

    base_cmd = get_hyperfine_base_cmd()
    cmd = base_cmd + [
        "--warmup", str(warmup),
        "--runs", str(runs),
        "--export-json", str(temp_json),
    ] + cmd_strs

    # Every subprocess.run below is bounded: a benchmark that never terminates
    # must fail this one entry, not wedge the suite.
    def _run(c):
        return subprocess.run(
            c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=HYPERFINE_TIMEOUT_S,
        )

    try:
        proc = _run(cmd)
        if proc.returncode != 0 and base_cmd[0] != "mise":
            cmd = ["mise", "exec", "--"] + cmd
            _run(cmd)
    except FileNotFoundError:
        cmd = ["mise", "exec", "--"] + cmd
        try:
            _run(cmd)
        except subprocess.TimeoutExpired:
            temp_json.unlink(missing_ok=True)
            return {}
    except subprocess.TimeoutExpired:
        print(
            f"  {YELLOW}timed out after {HYPERFINE_TIMEOUT_S}s - reported as "
            f"failed, continuing{RESET}",
            flush=True,
        )
        temp_json.unlink(missing_ok=True)
        return {}

    res_by_id = {}
    if temp_json.exists():
        try:
            if temp_json.stat().st_size > 0:
                with open(temp_json, "r") as f:
                    data = json.load(f)
                results = data.get("results", [])
                for idx, r_id in enumerate(r_order):
                    if idx < len(results):
                        res_by_id[r_id] = results[idx]
        except (json.JSONDecodeError, OSError):
            pass
        finally:
            temp_json.unlink(missing_ok=True)
    return res_by_id

def draw_header_box(versions: dict, width=96) -> str:
    r_names = ", ".join(f"{r['color']}{r['name']}{RESET}" for r in RUNTIMES)
    v_strs = " | ".join(f"{r['color']}{r['name']}{RESET}: {versions.get(r['id'], 'unknown')}" for r in RUNTIMES)
    lines = [
        f"{BOLD}{MAGENTA}JS RUNTIME BENCHMARK SUITE: 5-WAY COMPARISON{RESET}",
        f"{DIM}Target Runtimes: {r_names}{RESET}",
        f"{DIM}Detected Versions: {v_strs}{RESET}",
        f"{DIM}Metrics: Execution Time (Hyperfine), Binary Size & Memory Usage (Peak RSS){RESET}"
    ]
    box = []
    box.append("╔" + "═" * (width - 2) + "╗")
    for l in lines:
        box.append("║  " + pad_cell(l, width - 6, "center") + "  ║")
    box.append("╚" + "═" * (width - 2) + "╝")
    return "\n".join(box)

def draw_startup_floor_box(floors: dict, runtimes: list, width=96) -> str:
    lines = [
        f"{BOLD}{MAGENTA}PROCESS STARTUP FLOOR{RESET}",
        "─" * (width - 6),
        f"{BOLD}{pad_cell('Runtime', 14)} {pad_cell('Median startup', 20, 'right')} "
        f"{pad_cell('vs fastest', 16, 'right')}{RESET}",
        "─" * (width - 6),
    ]

    present = [r for r in runtimes if r["id"] in floors]
    if not present:
        return "\n".join(lines + ["  (unavailable)", "─" * (width - 6)])

    best = min(floors[r["id"]] for r in present)
    for r in sorted(present, key=lambda r: floors[r["id"]]):
        ms = floors[r["id"]]
        rel = "fastest" if ms <= best else f"{ms / best:.2f}x"
        name_col = f"{r['color']}{pad_cell(r['name'], 14)}{RESET}"
        lines.append(
            f"{name_col} {pad_cell(f'{ms:.2f} ms', 20, 'right')} "
            f"{pad_cell(rel, 16, 'right')}"
        )

    lines.append("─" * (width - 6))
    lines.append(
        f"{DIM}  Subtracted from every mean below to give work time - without it a"
        f" few-ms{RESET}"
    )
    lines.append(f"{DIM}  benchmark reports mostly process startup.{RESET}")
    return "\n".join(lines)

def draw_binary_size_box(bin_map: dict, width=96) -> str:
    lines = [
        f"{BOLD}{MAGENTA}RUNTIME BINARY SIZE COMPARISON{RESET}",
        "─" * (width - 6),
        f"{BOLD}{pad_cell('Runtime', 14)} {pad_cell('Binary Path', 52)} {pad_cell('Size (MB)', 14, 'right')}{RESET}",
        "─" * (width - 6),
    ]

    sizes = {}
    for r in RUNTIMES:
        r_id = r["id"]
        b_p = bin_map.get(r_id, Path(r_id))
        sz = b_p.stat().st_size / (1024 * 1024) if b_p.exists() else 0.0
        sizes[r_id] = sz

    sorted_r = sorted(RUNTIMES, key=lambda r: sizes.get(r["id"], 0.0))
    for r in sorted_r:
        r_id = r["id"]
        sz = sizes[r_id]
        b_p = bin_map.get(r_id, Path(r_id))
        path_str = str(b_p.relative_to(ROOT_DIR)) if b_p.is_relative_to(ROOT_DIR) else str(b_p)
        name_col = f"{r['color']}{pad_cell(r['name'], 14)}{RESET}"
        lines.append(f"{name_col} {pad_cell(path_str, 52)} {pad_cell(f'{sz:.2f} MB', 14, 'right')}")

    lines.append("─" * (width - 6))

    ant_sz = sizes.get("ant", 0.0)
    tjs_sz = sizes.get("tjs", 0.0)
    if ant_sz > 0 and tjs_sz > 0:
        if ant_sz <= tjs_sz:
            ratio = tjs_sz / ant_sz
            h2h_str = f"{BOLD}Head-to-Head (ant vs txiki.js):{RESET} {GREEN}ant{RESET} is {ant_sz:.2f} MB ({GREEN}{ratio:.2f}x smaller{RESET} than txiki.js {tjs_sz:.2f} MB)"
        else:
            ratio = ant_sz / tjs_sz
            h2h_str = f"{BOLD}Head-to-Head (ant vs txiki.js):{RESET} {YELLOW}txiki.js{RESET} is {tjs_sz:.2f} MB ({YELLOW}{ratio:.2f}x smaller{RESET} than ant {ant_sz:.2f} MB)"
    else:
        smallest = sorted_r[0]
        h2h_str = f"{GREEN}⚡ {smallest['color']}{smallest['name']}{RESET} is smallest ({sizes[smallest['id']]:.2f} MB)"

    lines.append(pad_cell(h2h_str, width - 6, "center"))

    box = []
    box.append("┌" + "─" * (width - 2) + "┐")
    for l in lines:
        box.append("│  " + pad_cell(l, width - 6) + "  │")
    box.append("└" + "─" * (width - 2) + "┘")
    return "\n".join(box)

def draw_benchmark_box(bench_info: dict, bench_results: dict, rss_map: dict,
                       startup_floor: dict | None = None, width=96) -> str:
    b_name = f"{BOLD}{CYAN}{bench_info['name']}{RESET}"
    b_desc = f"{DIM}{bench_info['desc']}{RESET}"
    floors = startup_floor or {}

    lines = [
        f"{b_name} - {b_desc}",
        "─" * (width - 6),
        f"{BOLD}Runtime          Best Time (ms)        Work (ms)       Peak RSS{RESET}",
        "─" * (width - 6),
    ]

    # Only runtimes that actually ran this benchmark: the fast tier drops two,
    # and the Ant-only group drops four. Printing 0.00 for the rest reads as a
    # result of zero rather than "not run".
    r_means = {}
    for r in RUNTIMES:
        r_id = r["id"]
        if r_id not in rss_map:
            continue
        res = bench_results.get(r_id, {})
        # Best sample, not the mean: that is what gets gated on, so it is what
        # the table should show. stddev still rides along as the spread.
        best = res.get(BEST_METRIC, 0.0) * 1000.0
        stddev = res.get("stddev", 0.0) * 1000.0
        rss = rss_map.get(r_id, 0.0)
        r_means[r_id] = best

        # Work time strips this runtime's process startup out, so a short
        # benchmark is not reported as a startup comparison.
        work = max(best - floors.get(r_id, 0.0), 0.0) if best else 0.0
        pct = (work / best * 100.0) if best > 0 else 0.0

        name_colored = f"{r['color']}{pad_cell(r['name'], 12)}{RESET}"
        lines.append(
            f"{name_colored}     {best:>8.2f} ± {stddev:<5.2f}    "
            f"{work:>8.2f} ({pct:>3.0f}%)    {rss:>6.1f} MB"
        )

    lines.append("─" * (width - 6))

    ant_m = r_means.get("ant", 0.0)
    tjs_m = r_means.get("tjs", 0.0)
    if ant_m > 0 and tjs_m > 0:
        if ant_m <= tjs_m:
            ratio = tjs_m / ant_m
            h2h_str = f"{BOLD}Head-to-Head:{RESET} {GREEN}ant{RESET} ({ant_m:.2f} ms) vs {YELLOW}txiki.js{RESET} ({tjs_m:.2f} ms) ➔ {GREEN}ant is {ratio:.2f}x faster{RESET}"
        else:
            ratio = ant_m / tjs_m
            h2h_str = f"{BOLD}Head-to-Head:{RESET} {GREEN}ant{RESET} ({ant_m:.2f} ms) vs {YELLOW}txiki.js{RESET} ({tjs_m:.2f} ms) ➔ {YELLOW}txiki.js is {ratio:.2f}x faster{RESET}"
    else:
        valid_means = [(r_id, m) for r_id, m in r_means.items() if m > 0]
        if valid_means:
            valid_means.sort(key=lambda x: x[1])
            w_id, w_m = valid_means[0]
            w_name = next(r["name"] for r in RUNTIMES if r["id"] == w_id)
            w_color = next(r["color"] for r in RUNTIMES if r["id"] == w_id)
            h2h_str = f"{GREEN}⚡ {w_color}{w_name}{RESET} is fastest ({w_m:.2f} ms)"
        else:
            h2h_str = "N/A"

    lines.append(pad_cell(h2h_str, width - 6, "center"))

    box = []
    box.append("┌" + "─" * (width - 2) + "┐")
    for l in lines:
        box.append("│  " + pad_cell(l, width - 6) + "  │")
    box.append("└" + "─" * (width - 2) + "┘")
    return "\n".join(box)

def draw_summary_table(summary_data: list, width=96) -> str:
    lines = [
        f"{BOLD}{MAGENTA}FINAL EXECUTION TIME SUMMARY (Best Time in ms){RESET}",
        "─" * (width - 6),
    ]

    bench_short_names = [item["name"].split()[0] for item in summary_data]
    header_cols = [pad_cell("Runtime", 14)]
    for b_short in bench_short_names:
        header_cols.append(pad_cell(b_short, 10, "right"))
    header_cols.append(pad_cell("Perf Wins", 12, "right"))

    lines.append(f"{BOLD}{' '.join(header_cols)}{RESET}")
    lines.append("─" * (width - 6))

    wins = {r["id"]: 0 for r in RUNTIMES}
    for item in summary_data:
        means = item.get("best") or item["means"]
        valid = [(r_id, m) for r_id, m in means.items() if m > 0]
        if valid:
            valid.sort(key=lambda x: x[1])
            winner_id = valid[0][0]
            wins[winner_id] += 1

    for r in RUNTIMES:
        r_id = r["id"]
        # Skip runtimes that ran nothing at all - the fast tier excludes two.
        if not any((item.get("best") or item["means"]).get(r_id, 0.0) > 0 for item in summary_data):
            continue
        r_color = r.get("color", "")
        row = [pad_cell(f"{r_color}{r['name']}{RESET}", 14)]

        for item in summary_data:
            m_val = (item.get("best") or item["means"]).get(r_id, 0.0)
            # "-" distinguishes a benchmark this runtime did not run (the
            # Ant-only group) from one that measured zero.
            cell = f"{m_val:.2f}" if m_val > 0 else "-"
            row.append(pad_cell(cell, 10, "right"))

        w_cnt = wins[r_id]
        row.append(pad_cell(f"{w_cnt}", 12, "right"))
        lines.append(" ".join(row))

    lines.append("─" * (width - 6))

    ant_wins = 0
    tjs_wins = 0
    total_b = len(summary_data)
    for item in summary_data:
        means = item["means"]
        ant_m = means.get("ant", 0.0)
        tjs_m = means.get("tjs", 0.0)
        if ant_m > 0 and tjs_m > 0:
            if ant_m <= tjs_m:
                ant_wins += 1
            else:
                tjs_wins += 1

    summary_str = f"{BOLD}Head-to-Head (ant vs txiki.js):{RESET} {GREEN}ant{RESET} won {ant_wins}/{total_b} benchmarks | {YELLOW}txiki.js{RESET} won {tjs_wins}/{total_b}"
    lines.append(pad_cell(summary_str, width - 6, "center"))

    box = []
    box.append("╔" + "═" * (width - 2) + "╗")
    for l in lines:
        box.append("║  " + pad_cell(l, width - 6) + "  ║")
    box.append("╚" + "═" * (width - 2) + "╝")
    return "\n".join(box)

def draw_memory_summary_table(summary_data: list, width=96) -> str:
    lines = [
        f"{BOLD}{MAGENTA}FINAL PEAK RSS MEMORY USAGE SUMMARY (in MB){RESET}",
        "─" * (width - 6),
    ]

    bench_short_names = [item["name"].split()[0] for item in summary_data]
    header_cols = [pad_cell("Runtime", 14)]
    for b_short in bench_short_names:
        header_cols.append(pad_cell(b_short, 10, "right"))
    header_cols.append(pad_cell("Avg RSS", 10, "right"))
    header_cols.append(pad_cell("Mem Wins", 10, "right"))

    lines.append(f"{BOLD}{' '.join(header_cols)}{RESET}")
    lines.append("─" * (width - 6))

    wins = {r["id"]: 0 for r in RUNTIMES}
    for item in summary_data:
        rss_map = item["rss"]
        valid = [(r_id, rss) for r_id, rss in rss_map.items() if rss > 0]
        if valid:
            valid.sort(key=lambda x: x[1])
            winner_id = valid[0][0]
            wins[winner_id] += 1

    for r in RUNTIMES:
        r_id = r["id"]
        # Same as the time summary: skip runtimes this run never exercised, and
        # mark per-benchmark gaps as "-" rather than 0.0 MB.
        if not any(item["rss"].get(r_id, 0.0) > 0 for item in summary_data):
            continue
        r_color = r.get("color", "")
        row = [pad_cell(f"{r_color}{r['name']}{RESET}", 14)]

        rss_vals = []
        for item in summary_data:
            rss_val = item["rss"].get(r_id, 0.0)
            if rss_val > 0:
                rss_vals.append(rss_val)
            row.append(pad_cell(f"{rss_val:.1f}" if rss_val > 0 else "-", 10, "right"))

        avg_rss = (sum(rss_vals) / len(rss_vals)) if rss_vals else 0.0
        row.append(pad_cell(f"{avg_rss:.1f}", 10, "right"))
        row.append(pad_cell(f"{wins[r_id]}", 10, "right"))
        lines.append(" ".join(row))

    lines.append("─" * (width - 6))

    ant_rss = [item["rss"].get("ant", 0.0) for item in summary_data if item["rss"].get("ant", 0.0) > 0]
    tjs_rss = [item["rss"].get("tjs", 0.0) for item in summary_data if item["rss"].get("tjs", 0.0) > 0]
    avg_ant = (sum(ant_rss) / len(ant_rss)) if ant_rss else 0.0
    avg_tjs = (sum(tjs_rss) / len(tjs_rss)) if tjs_rss else 0.0

    if avg_ant > 0 and avg_tjs > 0:
        if avg_ant <= avg_tjs:
            ratio = avg_tjs / avg_ant
            mem_h2h = f"{BOLD}Head-to-Head Memory (ant vs txiki.js):{RESET} {GREEN}ant{RESET} avg peak RSS {avg_ant:.1f} MB vs {YELLOW}txiki.js{RESET} {avg_tjs:.1f} MB ({GREEN}ant uses {ratio:.2f}x less memory{RESET})"
        else:
            ratio = avg_ant / avg_tjs
            mem_h2h = f"{BOLD}Head-to-Head Memory (ant vs txiki.js):{RESET} {GREEN}ant{RESET} avg peak RSS {avg_ant:.1f} MB vs {YELLOW}txiki.js{RESET} {avg_tjs:.1f} MB ({YELLOW}txiki.js uses {ratio:.2f}x less memory{RESET})"
    else:
        mem_h2h = "N/A"

    lines.append(pad_cell(mem_h2h, width - 6, "center"))

    box = []
    box.append("╔" + "═" * (width - 2) + "╗")
    for l in lines:
        box.append("║  " + pad_cell(l, width - 6) + "  ║")
    box.append("╚" + "═" * (width - 2) + "╝")
    return "\n".join(box)

def save_bench_json_and_baseline(bin_map: dict, versions: dict, summary_results: list,
                                 update_baseline: bool = False, tier: str = "full",
                                 startup_floor: dict | None = None) -> tuple[Path, Path | None]:
    from datetime import datetime, timezone
    from compliance_common import git_revision

    logs_dir = ROOT_DIR.parent / ".deps" / "compliance" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    manifest_path = logs_dir / f"bench_{ts}.json"
    latest_path = logs_dir / "bench-latest.json"

    rev = git_revision()

    manifest_data = {
        "schema_version": 2,
        "type": "performance_benchmark",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "revision": rev,
        # Which tier produced this. A fast run covers a subset of benchmarks
        # and runtimes; it diffs against the full baseline fine (the workloads
        # are identical) but must never be promoted to one.
        "tier": tier,
        # Per-runtime process startup, subtracted from each mean to get "work".
        "startup_floor_ms": startup_floor or {},
        "runtimes": {
            r["id"]: {
                "name": r["name"],
                "version": versions.get(r["id"], "unknown"),
                "binary_path": str(bin_map.get(r["id"], "")),
                # Recorded so a later run can gate on binary growth, not just
                # on speed.
                "binary_size": (
                    bin_map[r["id"]].stat().st_size
                    if bin_map.get(r["id"]) and bin_map[r["id"]].exists() else 0
                ),
            } for r in RUNTIMES
        },
        "benchmarks": summary_results
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        f.write("\n")

    try:
        if latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        latest_path.symlink_to(manifest_path.name)
    except Exception:
        pass

    baseline_written = None
    if update_baseline and tier != "full":
        # A fast manifest is missing most of the suite. Promoting it would
        # silently shrink the baseline to whatever the fast tier happened to
        # cover, and every absent benchmark would then read as "added".
        print(
            f"{YELLOW}--update-baseline ignored: this was a --fast run. "
            f"Seed the baseline from a full run.{RESET}",
            flush=True,
        )
    elif update_baseline:
        baseline_path = ROOT_DIR.parent / "docs" / "repo" / "bench-baseline.json"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
            f.write("\n")
        baseline_written = baseline_path

    return manifest_path, baseline_written

def flag_value(name: str, default: float) -> float:
    """Read `--flag N` or `--flag=N` from argv."""
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            try:
                return float(sys.argv[i + 1])
            except ValueError:
                return default
        if a.startswith(name + "="):
            try:
                return float(a.split("=", 1)[1])
            except ValueError:
                return default
    return default


def check_thresholds(manifest_path: Path, speed_lag: float, size_growth: float) -> int:
    """Gate this run against the checked-in baseline.

    Lives in scripts/bench_baseline.py so that the same comparison backs both
    `just bench-diff` and CI. Returns the exit code to propagate.
    """
    script = ROOT_DIR.parent / "scripts" / "bench_baseline.py"
    if not script.exists():
        print(f"{RED}--check-thresholds: {script} is missing.{RESET}", flush=True)
        return 1

    baseline = ROOT_DIR.parent / "docs" / "repo" / "bench-baseline.json"
    if not baseline.exists():
        # Nothing to compare against yet. Say so loudly rather than exiting 0
        # and looking like a gate that passed.
        print(
            f"{YELLOW}--check-thresholds: no baseline at {baseline}; "
            f"nothing to gate against. Seed one with "
            f"`just bench-update-baseline`.{RESET}",
            flush=True,
        )
        return 1

    print(flush=True)
    return subprocess.run([
        sys.executable, str(script), "diff", str(manifest_path),
        "--threshold", str(speed_lag),
        "--size-threshold", str(size_growth),
    ]).returncode


def main():
    force_update = "--update-binaries" in sys.argv
    update_baseline = "--update-baseline" in sys.argv
    # CI on `main` and `upstream` passes these; before this they were parsed by
    # nothing and the job could not fail.
    do_check = "--check-thresholds" in sys.argv
    fast = "--fast" in sys.argv
    speed_lag = flag_value("--max-speed-lag", 10.0)
    size_growth = flag_value("--max-size-growth", 25.0)

    # Fast tier: fewer benchmarks, three runtimes, fewer runs - sized to fit an
    # edit-test loop. The workloads are identical to the full tier, so a fast
    # manifest diffs against the same baseline; only its coverage is narrower.
    if fast:
        benchmarks = [b for b in BENCHMARKS if b.get("tier") == "fast"]
        runtimes = [r for r in RUNTIMES if r.get("fast")]
    else:
        benchmarks = list(BENCHMARKS)
        runtimes = list(RUNTIMES)

    # Identical sampling in both tiers. The gating metric is the fastest sample
    # (see BEST_METRIC below), and min is biased by how many samples it picks
    # from - min of 10 runs sits ~0.7% below min of 5 on the same workload. Since
    # a fast manifest diffs against a full baseline, differing run counts would
    # inject that bias as a phantom regression on every fast run.
    warmup, runs = WARMUP_RUNS, TIMED_RUNS

    bin_map, asset_info = ensure_binaries(force_update=force_update)
    ensure_js_bundles(bin_map.get("tjs", resolve_binary("tjs")))

    versions = {r["id"]: get_runtime_version(bin_map[r["id"]], r["id"]) for r in RUNTIMES}
    update_version_manifest(bin_map, versions, asset_info)

    print(flush=True)
    print(draw_header_box(versions), flush=True)
    print(flush=True)
    print(draw_binary_size_box(bin_map), flush=True)
    print(flush=True)

    if fast:
        print(
            f"  {YELLOW}fast tier{RESET}: {len(benchmarks)}/{len(BENCHMARKS)} benchmarks, "
            f"{len(runtimes)}/{len(RUNTIMES)} runtimes, {runs} runs. "
            f"Run the full suite for release-quality numbers.",
            flush=True,
        )
        print(flush=True)

    startup_floor = measure_startup_floor(bin_map, runtimes)
    print(draw_startup_floor_box(startup_floor, runtimes), flush=True)
    print(flush=True)

    summary_results = []

    for b in benchmarks:
        # A benchmark may restrict itself to a subset of runtimes - the Ant-only
        # group covers subsystems with no portable cross-runtime API.
        allowed = b.get("runtimes")
        cmds_map = {}
        for r in runtimes:
            r_id = r["id"]
            if allowed is not None and r_id not in allowed:
                continue
            bin_p = bin_map[r_id]
            if not bin_p or not bin_p.exists():
                continue
            file_path = BENCH_DIR / (b["ts"] if r["ts_file"] else b["js"])
            cmds_map[r_id] = [str(bin_p)] + r["args"] + [str(file_path)]

        print(f"⏳ Running Benchmark: {CYAN}{b['name']}{RESET}...", flush=True)

        bench_results = run_hyperfine(cmds_map, warmup=warmup, runs=runs)

        rss_map = {}
        for r_id, cmd in cmds_map.items():
            rss_map[r_id] = measure_peak_rss(cmd)

        print(draw_benchmark_box(b, bench_results, rss_map, startup_floor), flush=True)
        print(flush=True)

        # stddev and median ride along with the mean: scripts/bench_baseline.py
        # needs the run-to-run spread to tell a real regression from noise, and
        # the median to sanity-check a mean skewed by one slow outlier. Nothing
        # in the tables below reads them.
        means = {}
        stddev = {}
        median = {}
        best = {}
        work = {}
        for r in RUNTIMES:
            r_id = r["id"]
            res = bench_results.get(r_id, {})
            means[r_id] = res.get("mean", 0.0) * 1000.0
            stddev[r_id] = res.get("stddev", 0.0) * 1000.0
            median[r_id] = res.get("median", 0.0) * 1000.0
            # The gating metric: fastest sample, least contaminated by whatever
            # else the machine was doing. means/stddev/median stay recorded for
            # diagnostics and for reading old manifests.
            best[r_id] = res.get(BEST_METRIC, 0.0) * 1000.0
            # Best minus this runtime's startup floor: what the benchmark
            # actually spent, with process startup taken out. Clamped at zero
            # so a benchmark at or below the floor reads as 0 rather than
            # negative. coldstart deliberately measures the floor itself, so
            # its work time being ~0 is the correct answer, not a bug.
            floor = startup_floor.get(r_id, 0.0)
            work[r_id] = max(best[r_id] - floor, 0.0) if best[r_id] else 0.0

        summary_results.append({
            "name": b["name"],
            "id": b["id"],
            "means": means,
            "stddev": stddev,
            "median": median,
            "best": best,
            "work": work,
            "rss": rss_map
        })

    print(draw_summary_table(summary_results), flush=True)
    print(flush=True)
    print(draw_memory_summary_table(summary_results), flush=True)
    print(flush=True)

    manifest_path, baseline_path = save_bench_json_and_baseline(
        bin_map, versions, summary_results, update_baseline=update_baseline,
        tier="fast" if fast else "full", startup_floor=startup_floor,
    )
    print(f"  {CYAN}Benchmark Manifest JSON : {manifest_path}{RESET}", flush=True)
    if baseline_path:
        print(f"  {GREEN}Benchmark Baseline Updated: {baseline_path}{RESET}", flush=True)

    if do_check:
        sys.exit(check_thresholds(manifest_path, speed_lag, size_growth))

if __name__ == "__main__":
    main()
