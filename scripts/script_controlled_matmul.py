#!/usr/bin/env python3
# Copy of script_controlled.py, adapted to call matmul_controlled.py.
import subprocess
import pandas as pd
import os
import time
import re
import argparse

# ------------------ ARGUMENTS ------------------
parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", type=str, default=None)
args = parser.parse_args()

target_size = os.environ.get("TARGET_SIZE_KB")
if target_size:
    sizes_kb = [int(target_size)]
else:
    sizes_kb = [65536]  # 64MB per matrix by default

results = []

POD_ID = os.environ.get("POD_ID", "local")
output_dir = args.output_dir if args.output_dir else f"results/{POD_ID}/perf/matmul"
os.makedirs(output_dir, exist_ok=True)
print(f"[INFO] Results will be saved in: {output_dir}")


def run_perf_matmul(size_kb):
    size_bytes = int(size_kb * 1024)
    ops_or_bw = 0.0
    lat_ns = min_ns = max_ns = std_ns = 0.0

    EXPERIMENT_MODE = os.environ.get("EXPERIMENT_MODE", "standard")
    MATMUL_OP = os.environ.get("MATMUL_OP", "gemm")   # "gemm" (default) or "gemv"

    cmd = [
        "perf", "stat",
        "-e", "cycles,instructions,L1-dcache-load-misses,LLC-load-misses,dTLB-load-misses,stalled-cycles-frontend,stalled-cycles-backend",
        "-x", ";",
        "python3", "scripts/matmul_controlled.py",
        "--mode", "matmul",
        "--size-bytes", str(size_bytes),
        "--op", MATMUL_OP
    ]

    if EXPERIMENT_MODE == "time":
        cmd.extend(["--duration", "60"])
        print(f"Running: matmul, {size_kb} KB/matrix (Mode: TIME BOUND 60s)")
    elif EXPERIMENT_MODE == "work":
        TARGET_MB = os.environ.get("MATMUL_TARGET_MB", "10240")
        cmd.extend(["--target-mb", TARGET_MB])
        print(f"Running: matmul, {size_kb} KB/matrix (Mode: WORK BOUND {TARGET_MB}MB)")
    else:
        cmd.extend(["--iters", "50"])
        print(f"Running: matmul, {size_kb} KB/matrix (Mode: STANDARD 50 iters)")

    proc = subprocess.run(cmd, capture_output=True, text=True)

    # -------- PARSING (identical to script_controlled.py) --------
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "|" in line:
            parts = line.split("|")
            for part in parts:
                part = part.strip()
                if "BW:" in part:
                    bw_str = part.split(":")[1].replace("GB/s", "").strip()
                    ops_or_bw = float(bw_str)
                elif "Lat:" in part:
                    lat_match = re.search(r"Lat:\s*([0-9.]+)", part)
                    min_match = re.search(r"Min:\s*([0-9.]+)", part)
                    max_match = re.search(r"Max:\s*([0-9.]+)", part)
                    std_match = re.search(r"Std:\s*([0-9.]+)", part)
                    if lat_match: lat_ns = float(lat_match.group(1))
                    if min_match: min_ns = float(min_match.group(1))
                    if max_match: max_ns = float(max_match.group(1))
                    if std_match: std_ns = float(std_match.group(1))

    metrics = {"cycles": 0, "instructions": 0, "L1_misses": 0, "LLC_misses": 0, "TLB_misses": 0}
    for line in proc.stderr.splitlines():
        parts = line.strip().split(";")
        if len(parts) < 3:
            continue
        try:
            val_str = parts[0].replace(",", "").replace(" ", "")
            if not val_str or val_str == "<not":
                continue
            val = int(float(val_str))
            event = parts[2]
            if "cycles" in event: metrics["cycles"] = val
            elif "instructions" in event: metrics["instructions"] = val
            elif "L1-dcache-load-misses" in event: metrics["L1_misses"] = val
            elif "LLC-load-misses" in event: metrics["LLC_misses"] = val
            elif "dTLB-load-misses" in event: metrics["TLB_misses"] = val
        except (ValueError, IndexError):
            continue

    ipc = metrics["instructions"] / metrics["cycles"] if metrics["cycles"] > 0 else 0

    if ops_or_bw == 0.0:
        print(f"ERROR : Parsing failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr[:500]}")
        return None

    print(f"OK (IPC: {ipc:.2f})")
    return {
        "pattern": "matmul", "size_kb": size_kb, "ops_or_bw": ops_or_bw,
        "lat_ns": lat_ns, "min_ns": min_ns, "max_ns": max_ns, "std_ns": std_ns,
        "IPC": ipc, "L1_misses": metrics["L1_misses"], "LLC_misses": metrics["LLC_misses"],
        "TLB_misses": metrics["TLB_misses"], "cycles": metrics["cycles"],
    }


for size_kb in sizes_kb:
    results.append(run_perf_matmul(size_kb))

df = pd.DataFrame(results)
EXPERIMENT_MODE = os.environ.get("EXPERIMENT_MODE", "standard")
MATMUL_OP = os.environ.get("MATMUL_OP", "gemm")
csv_path = os.path.join(output_dir, f"matmul_benchmark_{MATMUL_OP}_{EXPERIMENT_MODE}.csv")
df.to_csv(csv_path, index=False)

print("\n=== PERFORMANCE OVERVIEW ===")
print(df.to_string(index=False))
print(f"\n=== FINISHED: Results saved in {csv_path} ===")