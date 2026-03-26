import matplotlib.pyplot as plt
import mem_stress2
import numpy as np
import os

def run_comparison():
    print("=== Min/Max Analysis: Benchmark in Kilobytes (KB) ===")
    
    # LISTE EN KILO-OCTETS (Ko)
    # 32 Ko = L1 typique
    # 256 Ko = L2 typique
    # 4096 Ko (4 Mo) et plus = L3 puis RAM
    target_sizes_kb = [1, 2, 4, 6, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536]
    
    output_dir = "results/analysis_4modes"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    data = {
        'Seq Read':   {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#1f77b4'},
        'Seq Write':  {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#d62728'},
        'Rand Read':  {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#ff7f0e'},
        'Rand Write': {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#2ca02c'}
    }
    
    ITERS_SEQ = 20000   # Number of full passes over the array
    ITERS_RAND = 20000  # Number of batches of access
    BATCH_SIZE = 20000

    for size_kb in target_sizes_kb:
        
        if size_kb < 1024:
            print(f"--- Benchmarking : {size_kb} Ko ---")
        else:
            print(f"--- Benchmarking : {size_kb/1024:.1f} Mo ---")
        
        # --- CONVERSION : Kilo -> Bytes ---
        real_size_bytes = int(size_kb * 1024)
        
        # 1. SEQUENTIAL READ
        mem_stress2.sequential_read(real_size_bytes, 5000)
        res_sr = mem_stress2.sequential_read(real_size_bytes, ITERS_SEQ)
        avg, mini, maxi, std = res_sr[2] , res_sr[3], res_sr[4], res_sr[8]
        
        data['Seq Read']['x'].append(size_kb) # Axe X in Ko
        data['Seq Read']['y'].append(avg)
        data['Seq Read']['std'].append(std)
        data['Seq Read']['y_err_low'].append(avg - mini) 
        data['Seq Read']['y_err_high'].append(maxi - avg)

        # 2. SEQUENTIAL WRITE
        mem_stress2.sequential_write(real_size_bytes, 5000)
        res_sw = mem_stress2.sequential_write(real_size_bytes, ITERS_SEQ)
        avg, mini, maxi, std = res_sw[2] , res_sw[3], res_sw[4], res_sw[8]
        
        data['Seq Write']['x'].append(size_kb) # Axe X en Ko
        data['Seq Write']['y'].append(avg)
        data['Seq Write']['std'].append(std)
        data['Seq Write']['y_err_low'].append(avg - mini) 
        data['Seq Write']['y_err_high'].append(maxi - avg)
        
        # 2. RANDOM READ
        res_rr = mem_stress2.random_access_test(real_size_bytes, ITERS_RAND, batch=BATCH_SIZE)
        avg, mini, maxi, std = res_rr[2] , res_rr[3], res_rr[4], res_rr[8]
        
        data['Rand Read']['x'].append(size_kb)
        data['Rand Read']['y'].append(avg)
        data['Rand Read']['std'].append(std)
        data['Rand Read']['y_err_low'].append(avg - mini)
        data['Rand Read']['y_err_high'].append(maxi - avg)

        # 3. RANDOM WRITE
        res_rw = mem_stress2.random_access_test(real_size_bytes, ITERS_RAND, batch=BATCH_SIZE)
        avg, mini, maxi, std = res_rw[2] , res_rw[3], res_rw[4], res_rw[8]
        
        data['Rand Write']['x'].append(size_kb)
        data['Rand Write']['y'].append(avg)
        data['Rand Write']['std'].append(std)
        data['Rand Write']['y_err_low'].append(avg - mini)
        data['Rand Write']['y_err_high'].append(maxi - avg)

    # --- Tracé ---
    print("\n[INFO] Génération du graphique...")
    plt.figure(figsize=(12, 8))
    
    # Shift factors
    offsets = {
        'Seq Read':   0.75,  # Shifted Left
        'Seq Write':  0.90,
        'Rand Read':  1.10,  # Center
        'Rand Write': 1.25   # Shifted Right
    }

    for label, d in data.items():
        shifted_x = [val * offsets[label] for val in d['x']]
        asymmetric_error = [d['y_err_low'], d['y_err_high']]
        std_err = d['std']
        
        plt.errorbar(
            shifted_x, d['y'], 
            yerr=asymmetric_error, 
            label=label, color=d['c'], fmt='o', 
            linewidth=2, markersize=5, capsize=4, alpha=0.9, ecolor=d['c']
        )

    plt.xscale('log')
    plt.yscale('log')

    plt.xticks(
        ticks=target_sizes_kb, 
        labels=[str(s) for s in target_sizes_kb], 
        rotation=45
    )

    plt.xlabel('Memory Block Size (KB)', fontsize=12, fontweight='bold')
    plt.ylabel('Mean latency per element access (ns).', fontsize=12, fontweight='bold')
    plt.title(f'Memory Performance: L1 -> L2 -> RAM (KB Scale)({ITERS_SEQ} iters Seq / {ITERS_RAND} iters Rand)', fontsize=14)

    plt.grid(True, which="major", ls="-", alpha=0.6)
    plt.legend(fontsize=11, loc='upper left')

    save_path = os.path.join(output_dir, "micro_analysis_iterations.png")
    plt.savefig(save_path)
    print(f"[OK] Plot saved: {save_path}")
    plt.show()

if __name__ == "__main__":
    run_comparison()