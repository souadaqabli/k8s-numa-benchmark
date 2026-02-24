#!/usr/bin/env python3
import subprocess
import pandas as pd
import os
import time
import matplotlib.pyplot as plt

# ------------------ CONFIG ------------------
patterns = ["sequential_read", "sequential_write"] 

sizes_kb = [1, 2, 4, 6, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536]
ITERS_SEQ = 20000   
ITERS_RAND = 20000
batch = 20000


results = []
output_dir = "results/perf/seq"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)


# ------------------ NEW PLOTTING FUNCTION ------------------
def generate_scientific_plots(df, output_dir):
    """Generates correlation plots for each mode and the global IPC"""
    plt.style.use('seaborn-v0_8-muted')
    l3_limit_kb = 4096  #  specific limit 4 Mo

    # 1. IPC plot 
    plt.figure(figsize=(12, 7))
    for pattern in df['pattern'].unique():
        subset = df[df['pattern'] == pattern]
        plt.plot(subset['size_kb'], subset['IPC'], marker='o', label=pattern.replace("_", " "))
    
    plt.axvline(x=l3_limit_kb, color='red', linestyle='--', linewidth=2, label='Limite L3 (4Mo)')
    plt.xscale('log')
    plt.xlabel('Array Size (KB)')
    plt.ylabel('IPC (Instructions Per Cycle)')
    plt.title('CPU Efficiency (IPC) vs Working Set Size')
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.savefig(os.path.join(output_dir, "perf_ipc_vs_size_eng.png"))
    plt.close()

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
    """Runs mem_stress3.py with perf and collects hardware metrics"""

    if unit == "kb":
        size_bytes = int(size_val * 1024)
        print_size = f"{size_val} Ko"
    else: # mb
        size_bytes = int(size_val * 1024 * 1024)
        print_size = f"{size_val} Mo"
    
    # 1. INITIALISATION CRUCIALE (Évite UnboundLocalError)
    ops_or_bw = 0.0
    lat_ns = 0.0
    

    # Choix dynamique des itérations
    current_iters = ITERS_SEQ if "sequential" in mode else ITERS_RAND

    # Construction de la commande perf
    cmd = [
        "perf", "stat",
        "-e", "cycles,instructions,L1-dcache-load-misses,LLC-load-misses,dTLB-load-misses,stalled-cycles-frontend,stalled-cycles-backend",
        "-x", ";",
        "python3", "mem_stress3.py",
        "--mode", mode,
        "--size-bytes", str(size_bytes),
        "--iters", str(current_iters),
        "--batch", str(batch)
    ]

    if stride_val is not None:
        cmd.extend(["--stride-bytes", str(stride_val)])

    print(f"Running: {mode}, {print_size}")
    proc = subprocess.run(cmd, capture_output=True, text=True)


    # -------- PARSING ROBUSTE (Compatible avec les prints) --------
    for line in proc.stdout.splitlines():
        line = line.strip()
        # Format : "Seq Read ... | BW: 25.4 GB/s | Lat: 0.31 ns (Min: 0.15, Max: 0.45)"
        if "|" in line:
            parts = line.split("|")
            for part in parts:
                part = part.strip()

                if "BW:" in part:
                    # Extraction : "BW: 25.4 GB/s" → 25.4
                    #ops = float(part.split(":")[1].replace("GB/s", "").strip())
                    bw_str = part.split(":")[1].replace("GB/s", "").strip()
                    ops_or_bw = float(bw_str)

                elif "IOPS:" in part:
                    # Extraction : "IOPS: 346801487" → 346801487
                    iops_str = part.split(":")[1].strip()
                    ops_or_bw = float(iops_str)

                elif "Lat:" in part:
                    # Extraction : "Lat: 0.31 ns (Min: 0.15, Max: 0.45)" → 0.31
                    lat_str = part.split(":")[1].strip().split(" ")[0]
                    lat_ns = float(lat_str)

        elif "Stride" in line and "ops/s:" in line:
            ops = float(line.split("ops/s:")[1].strip())

    # -------- EXTRACTION PERF (Stderr) --------
    metrics = {
    "cycles": 0, 
    "instructions": 0, 
    "L1_misses": 0, 
    "LLC_misses": 0, 
    "TLB_misses": 0, 
    "stalled_frontend": 0, 
    "stalled_backend": 0
    }

    for line in proc.stderr.splitlines():
        parts = line.strip().split(";")
        if len(parts) < 3: 
            continue

        try:
            # Format perf : "12345;;<not counted>;cycles"
            val_str = parts[0].replace(",", "").replace(" ", "")
            if not val_str or val_str == "<not":
                continue

            #val = int(float(parts[0].replace(",", "")))
            val = int(float(val_str))
            event = parts[2]
           
            if "cycles" in event: 
                metrics["cycles"] = val
            elif "instructions" in event: 
                metrics["instructions"] = val
            elif "L1-dcache-load-misses" in event: 
                metrics["L1_misses"] = val
            elif "LLC-load-misses" in event: 
                metrics["LLC_misses"] = val
            elif "dTLB-load-misses" in event: 
                metrics["TLB_misses"] = val
        except: 
            continue

    # Calcul IPC
    ipc = metrics["instructions"] / metrics["cycles"] if metrics["cycles"] > 0 else 0

    # Vérification du parsing
    if ops_or_bw == 0.0:
        print(f"ERREUR : Parsing échoué")
        print(f"STDOUT:\n{proc.stdout}")
        print(f"STDERR:\n{proc.stderr[:500]}")
        return None
    
    print(f"OK (IPC: {ipc:.2f})")



    return {
        "pattern": mode,
        "size_kb": size_val if unit == "kb" else size_val * 1024,
        #"stride": stride_val if stride_val else 0,
        "ops_or_bw": ops_or_bw,
        "lat_ns": lat_ns,
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
df.to_csv(os.path.join(output_dir, "memory_benchmark_results_full_seq.csv"), index=False)
print("\n=== TERMINE ===")
#print(df)
print("\n=== PERFORMANCE OVERVIEW ===")
print(df[["pattern", "size_kb", "ops_or_bw", "lat_ns", "IPC","L1_misses","LLC_misses","TLB_misses"]].to_string(index=False))


generate_scientific_plots(df, output_dir)

print("\n=== FINISHED: Results and Graphics in 'results/perf' directory ===")