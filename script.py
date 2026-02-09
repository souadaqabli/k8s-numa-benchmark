#!/usr/bin/env python3
import subprocess
import pandas as pd
import os

# ------------------ CONFIG ------------------
patterns = ["sequential_read", "sequential_write", "random_read", "random_write"]
#sizes_mb = [2, 8, 1024]
sizes_kb = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536]
ITERS_SEQ = 10000   #kant 50
ITERS_RAND = 10000
batch = 20000
stride_list = [64, 256, 512, 1024, 2048, 4096, 8192]
fixed_size_for_stride = 512 
results = []
output_dir = "results"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

#-------------Topology--------------
def capture_system_topology():
    try:
        img_path = os.path.join(output_dir, "system_topology.png")
        subprocess.run(["lstopo", "--output-format", "png", img_path], check=False, stderr=subprocess.DEVNULL)
        print(f"Topology graphic saved in : {img_path}")
    except:
        print("lstopo non disponible")

# ------------------ FUNCTION ------------------
def run_perf(mode, size_val, unit="kb", stride_val=None):
    """Lance mem_stress.py avec perf et récupère les métriques"""

    if unit == "kb":
        size_bytes = int(size_val * 1024)
        print_size = f"{size_val} Ko"
    else: # mb
        size_bytes = int(size_val * 1024 * 1024)
        print_size = f"{size_val} Mo"
    
    # 1. INITIALISATION CRUCIALE (Évite UnboundLocalError)
    ops = 0.0
    lat = 0.0
    
    #size_bytes = size_mb * 1024 * 1024

    # Choix dynamique des itérations
    current_iters = ITERS_SEQ if "sequential" in mode else ITERS_RAND

    cmd = [
        "perf", "stat",
        "-e", "cycles,instructions,L1-dcache-load-misses,LLC-load-misses,dTLB-load-misses",
        "-x", ";",
        "python3", "mem_stress2.py",
        "--mode", mode,
        "--size-bytes", str(size_bytes),
        "--iters", str(current_iters),
        "--batch", str(batch)
    ]

    if stride_val is not None:
        cmd.extend(["--stride-bytes", str(stride_val)])

    #print(f"Running: {mode}, {size_mb}MiB")
    print(f"Running: {mode}, {print_size}")
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # -------- PARSING ROBUSTE (Compatible avec les prints) --------
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "|" in line:
            parts = line.split("|")
            for part in parts:
                part = part.strip()
                if "BW:" in part:
                    ops = float(part.split(":")[1].replace("GB/s", "").strip())
                elif "IOPS:" in part:
                    ops = float(part.split(":")[1].strip())
                elif "Lat:" in part:
                    # On ignore les (Min/Max) en prenant le premier mot après le ':'
                    raw_lat = part.split(":")[1].strip().split(" ")[0]
                    lat = float(raw_lat)
        elif "Stride" in line and "ops/s:" in line:
            ops = float(line.split("ops/s:")[1].strip())

    # -------- EXTRACTION PERF (Stderr) --------
    metrics = {"cycles": 0, "instructions": 0, "L1_misses": 0, "LLC_misses": 0, "TLB_misses": 0}
    for line in proc.stderr.splitlines():
        parts = line.strip().split(";")
        if len(parts) < 3: continue
        try:
            val = int(float(parts[0].replace(",", "")))
            c = parts[2]
            if "cycles" in c: metrics["cycles"] = val
            elif "instructions" in c: metrics["instructions"] = val
            elif "L1-dcache-load-misses" in c: metrics["L1_misses"] = val
            elif "LLC-load-misses" in c: metrics["LLC_misses"] = val
            elif "dTLB-load-misses" in c: metrics["TLB_misses"] = val
        except: continue

    ipc = metrics["instructions"] / metrics["cycles"] if metrics["cycles"] > 0 else 0

    return {
        "pattern": mode,
        #"size_mb": size_mb,
        "size_kb": size_val if unit == "kb" else size_val * 1024,
        "stride": stride_val if stride_val else 0,
        "ops_or_bw": ops,
        "lat_ns": lat,
        "IPC": ipc,
        "L1_misses": metrics["L1_misses"],
        "LLC_misses": metrics["LLC_misses"],
        "TLB_misses": metrics["TLB_misses"]
    }

# ------------------ RUN & SAVE ------------------
capture_system_topology()

for size_kb in sizes_kb:
    for mode in patterns:
        results.append(run_perf(mode, size_kb, unit="kb"))

for s in stride_list:
    results.append(run_perf("stride", fixed_size_for_stride, stride_val=s))

df = pd.DataFrame(results)
df.to_csv(os.path.join(output_dir, "memory_benchmark_results_full.csv"), index=False)
print("\n=== TERMINE ===")
#print(df)
# Affiche uniquement les colonnes essentielles pour ton analyse
print("\n=== APERÇU DES PERFORMANCES ===")
print(df[["pattern", "size_kb", "ops_or_bw", "lat_ns", "IPC","L1_misses","LLC_misses","TLB_misses"]].to_string(index=False))