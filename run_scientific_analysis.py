import subprocess
import matplotlib.pyplot as plt
import numpy as np
import os

# --- CONFIGURATION ---
OUTPUT_DIR = "results"
SIZES_KB = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536]
 
ITERS_RAND = 20000 
BATCH = 20000

def get_perf_metrics(size_bytes):
    """
    Lance mem_stress2 via perf avec un nombre d'itérations fixe.
    """
    cmd = [
        "perf", "stat",
        "-e", "LLC-load-misses,instructions,cycles",
        "-x", ";",
        "python3", "mem_stress2.py",
        "--mode", "random_read",
        "--size-bytes", str(size_bytes),
        "--iters", str(ITERS_RAND), # Utilisation de --iters au lieu de --duration
        "--batch", str(BATCH)
    ]
    
    try:
        # Exécution et capture des flux
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        # 1. Parsing Latence (depuis stdout du script python)
        lat_ns = 0
        for line in proc.stdout.splitlines():
            if "Lat:" in line:
                # Récupère la valeur entre 'Lat:' et 'ns'
                lat_ns = float(line.split("Lat:")[1].split("ns")[0].strip())

        # 2. Parsing Perf (depuis stderr de perf stat)
        llc_misses = 0; instr = 0; cycles = 0
        for line in proc.stderr.splitlines():
            parts = line.split(";")
            if len(parts) < 3: continue
            try:
                # perf stat -x; renvoie la valeur en premier champ
                val = int(float(parts[0].replace(",", "")))
                event = parts[2]
                if "LLC-load-misses" in event: llc_misses = val
                elif "instructions" in event: instr = val
                elif "cycles" in event: cycles = val
            except: continue

        # Normalisation MPKI (Misses Per Kilo-Instruction)
        mpki = (llc_misses / instr) * 1000 if instr > 0 else 0
        # IPC (Efficacité du pipeline CPU)
        ipc = instr / cycles if cycles > 0 else 0
        
        return lat_ns, mpki, ipc

    except Exception as e:
        print(f"Erreur sur {size_bytes} bytes: {e}")
        return 0, 0, 0

def run_analysis():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    x_sizes, y_lat, y_miss, y_ipc = [], [], [], []
    
    print(f"{'Taille (Ko)':<12} | {'Latence (ns)':<12} | {'MPKI':<10} | {'IPC':<8}")
    print("-" * 55)

    for kb in SIZES_KB:
        lat, miss_rate, ipc = get_perf_metrics(int(kb * 1024))
        x_sizes.append(kb)
        y_lat.append(lat)
        y_miss.append(miss_rate)
        y_ipc.append(ipc)
        print(f"{kb:<12} | {lat:<12.2f} | {miss_rate:<10.2f} | {ipc:<8.2f}")

    # Pearson Correlation 
    corr = np.corrcoef(y_lat, y_miss)[0, 1] if len(y_lat) > 2 else 0
    print(f"\n[STAT] Correlation Latency/Misses : {corr:.4f}")

    # --- Plot double axis---
    fig, ax1 = plt.subplots(figsize=(12, 7))
    
    # Axe de gauche : Latence (ns)
    color = 'tab:blue'
    ax1.set_xlabel('Taille du Bloc (Ko) - Log', fontweight='bold')
    ax1.set_ylabel('Latence par accès (ns)', color=color, fontweight='bold')
    ax1.plot(x_sizes, y_lat, color=color, marker='o', linewidth=2, label='Latence')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_xscale('log')
    ax1.set_xticks(SIZES_KB)
    ax1.set_xticklabels([str(s) for s in SIZES_KB], rotation=45)
    ax1.grid(True, which='major', alpha=0.3)

    # Axe de droite : Misses (MPKI)
    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('LLC Misses (MPKI)', color=color, fontweight='bold')
    ax2.plot(x_sizes, y_miss, color=color, marker='x', linestyle='--', linewidth=2, label='Cache Misses')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title(f'Scientific analysis : Latency vs Cache Misses\nCorrélation : {corr:.2f} | {ITERS_RAND} fixed iterations ', fontsize=13)
    
    fig.tight_layout()
    save_path = os.path.join(OUTPUT_DIR, "correlation_latency_misses.png")
    plt.savefig(save_path)
    print(f"\n[OK] Scientific plot generated : {save_path}")

if __name__ == "__main__":
    run_analysis()