#!/usr/bin/env python3
import subprocess
import pandas as pd
import os
import time
import re
import argparse
import matplotlib.pyplot as plt

# ------------------ ARGUMENTS ------------------
parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", type=str, default=None)
parser.add_argument("--pattern", type=str, choices=["all", "sequential", "random"], default="all")
args = parser.parse_args()

# ------------------ CONFIG ------------------
if args.pattern == "sequential":
    patterns = ["sequential_read", "sequential_write"]
elif args.pattern == "random":
    patterns = ["random_read", "random_write"]
else:
    patterns = ["sequential_read", "sequential_write", "random_read", "random_write"]

#sizes_kb = [1, 2, 4, 6, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536, 131072,  262144, 524288,  1048576]
#sizes_kb = [16384, 65536, 131072,  262144, 524288,  1048576]
# --- INJECTION DYNAMIQUE DE LA TAILLE ---
target_size = os.environ.get("TARGET_SIZE_KB")

if target_size:
    sizes_kb = [int(target_size)]
    print(f"[INFO] Mode Isolé activé : exécution unique pour {target_size} KB")
else:
    sizes_kb = [16384, 65536, 131072, 262144, 524288, 1048576]
# ----------------------------------------
ITERS_SEQ = 200   
ITERS_RAND = 200
batch = 5000

results = []

# ------------------ OUTPUT DIR ------------------
POD_ID = os.environ.get("POD_ID", "local")

if args.output_dir:
    output_dir = args.output_dir
else:
    output_dir = f"results/{POD_ID}/perf/seq"

os.makedirs(output_dir, exist_ok=True)
print(f"[INFO] Results will be saved in: {output_dir}")

#-------------Topology--------------
def capture_system_topology():
    """Captures system topology using lstopo"""
    try:
        img_path = os.path.join(output_dir, "system_topology.png")
        subprocess.run(["lstopo", "--output-format", "png", img_path],
        check=False, 
        stderr=subprocess.DEVNULL
        )
        print(f"Topology graphic saved in : {img_path}")
    except:
        print("lstopo utility not available")

# ------------------ FUNCTION ------------------
def run_perf(mode, size_val, unit="kb", stride_val=None):
    """Runs mem_stress_controlled.py with perf and collects hardware metrics"""

    if unit == "kb":
        size_bytes = int(size_val * 1024)
        print_size = f"{size_val} KB"
    else: # mb
        size_bytes = int(size_val * 1024 * 1024)
        print_size = f"{size_val} MB"
    
    # 1. INITIALIZATION 
    ops_or_bw = 0.0
    lat_ns = 0.0
    min_ns = 0.0
    max_ns = 0.0
    std_ns = 0.0
    
    current_iters = ITERS_SEQ if "sequential" in mode else ITERS_RAND
    EXPERIMENT_MODE = os.environ.get("EXPERIMENT_MODE", "standard")

    # Construction of perf command 
    cmd = [
        "perf", "stat",
        "-e", "cycles,instructions,L1-dcache-load-misses,LLC-load-misses,dTLB-load-misses,stalled-cycles-frontend,stalled-cycles-backend",
        "-x", ";",
        "python3", "scripts/mem_stress_controlled.py", # <-- Targets the new file
        "--mode", mode,
        "--size-bytes", str(size_bytes),
        "--batch", str(batch)
    ]

    if stride_val is not None:
        cmd.extend(["--stride-bytes", str(stride_val)])

    # --- MODE INJECTION ---
    if EXPERIMENT_MODE == "time":
        cmd.extend(["--duration", "60"]) # 60 seconds strict timer
        print(f"Running: {mode}, {print_size} (Mode: TIME BOUND 60s)")
    elif EXPERIMENT_MODE == "work":
        cmd.extend(["--target-mb", "10240"]) # Constant 10 GB
        print(f"Running: {mode}, {print_size} (Mode: WORK BOUND 10GB)")
    else:
        cmd.extend(["--iters", str(current_iters)])
        print(f"Running: {mode}, {print_size} (Mode: STANDARD {current_iters} iters)")

    proc = subprocess.run(cmd, capture_output=True, text=True)

    # -------- ROBUST PARSING --------
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "|" in line:
            parts = line.split("|")
            for part in parts:
                part = part.strip()
                if "BW:" in part:
                    bw_str = part.split(":")[1].replace("GB/s", "").strip()
                    ops_or_bw = float(bw_str)
                elif "IOPS:" in part:
                    iops_str = part.split(":")[1].strip()
                    ops_or_bw = float(iops_str)
                elif "Lat:" in part:
                    lat_match = re.search(r"Lat:\s*([0-9.]+)", part)
                    min_match = re.search(r"Min:\s*([0-9.]+)", part)
                    max_match = re.search(r"Max:\s*([0-9.]+)", part)
                    std_match = re.search(r"Std:\s*([0-9.]+)", part)

                    if lat_match: lat_ns = float(lat_match.group(1))
                    if min_match: min_ns = float(min_match.group(1))
                    if max_match: max_ns = float(max_match.group(1))
                    if std_match: std_ns = float(std_match.group(1))

        elif "Stride" in line and "ops/s:" in line:
            ops_or_bw = float(line.split("ops/s:")[1].strip())

    # -------- PERF EXTRACTION --------
    metrics = {
    "cycles": 0, "instructions": 0, "L1_misses": 0, "LLC_misses": 0, 
    "TLB_misses": 0, "stalled_frontend": 0, "stalled_backend": 0
    }

    for line in proc.stderr.splitlines():
        parts = line.strip().split(";")
        if len(parts) < 3: continue
        try:
            val_str = parts[0].replace(",", "").replace(" ", "")
            if not val_str or val_str == "<not": continue
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
        print(f"ERROR : Parsing failed")
        print(f"STDOUT:\n{proc.stdout}")
        print(f"STDERR:\n{proc.stderr[:500]}")
        return None
    
    print(f"OK (IPC: {ipc:.2f})")

    return {
        "pattern": mode,
        "size_kb": size_val if unit == "kb" else size_val * 1024,
        "ops_or_bw": ops_or_bw,
        "lat_ns": lat_ns,
        "min_ns": min_ns,
        "max_ns": max_ns,
        "std_ns": std_ns,
        "IPC": ipc,
        "L1_misses": metrics["L1_misses"],
        "LLC_misses": metrics["LLC_misses"],
        "TLB_misses": metrics["TLB_misses"],
        "stalled_frontend": metrics["stalled_frontend"], 
        "stalled_backend": metrics["stalled_backend"],   
        "cycles": metrics["cycles"]                     
    }

# ------------------ RUN & SAVE ------------------
capture_system_topology()

for size_kb in sizes_kb:
    for mode in patterns:
        results.append(run_perf(mode, size_kb, unit="kb"))

df = pd.DataFrame(results)

# 1. Retrieve the mode (time, work, or standard)
EXPERIMENT_MODE = os.environ.get("EXPERIMENT_MODE", "standard")

# 2. Shorten the pattern (sequential -> seq, random -> rand)
if args.pattern == "sequential":
    pat_short = "seq"
elif args.pattern == "random":
    pat_short = "rand"
else:
    pat_short = args.pattern

# 3. Create the smart filename
csv_filename = f"memory_benchmark_{pat_short}_{EXPERIMENT_MODE}.csv"
csv_path = os.path.join(output_dir, csv_filename)

df.to_csv(csv_path, index=False)
# ====================================================================

print("\n=== PERFORMANCE OVERVIEW ===")
print(df[["pattern", "size_kb", "ops_or_bw", "lat_ns", "std_ns", "IPC", "LLC_misses"]].to_string(index=False))
print(f"\n=== FINISHED: Results saved in {csv_path} ===")