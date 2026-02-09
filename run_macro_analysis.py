import matplotlib.pyplot as plt
import mem_stress2  # Assure-toi que c'est le nom de ton fichier modifié
import numpy as np
import os

def run_comparison():
    print("=== Analyse Temps de Parcours : L1 -> L2 -> L3 -> RAM ===")
    
    target_sizes_kb = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536]
    
    output_dir = "results"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    data = {
        'Seq Read':   {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#1f77b4'},
        'Seq Write':  {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#d62728'},
        'Rand Read':  {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#ff7f0e'},
        'Rand Write': {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#2ca02c'}
    }
    
    ITERS_SEQ = 10000  
    ITERS_RAND = 10000
    BATCH_SIZE = 20000

    for size_kb in target_sizes_kb:
        print(f"--- Benchmarking : {size_kb if size_kb < 1024 else size_kb/1024} {'Ko' if size_kb < 1024 else 'Mo'} ---")
        real_size_bytes = int(size_kb * 1024)
        
        # 1. SEQUENTIAL READ
        # On ignore les premiers retours pour prendre avg_total (index 5), min (index 6), max (index 7)
        res_seq = mem_stress2.sequential_read(real_size_bytes, ITERS_SEQ)
        avg_t, min_t, max_t, std = res_seq[5], res_seq[6], res_seq[7], res_seq[8]
        
        data['Seq Read']['x'].append(size_kb)
        data['Seq Read']['y'].append(avg_t / 1e6) # Conversion en ms
        data['Seq Read']['std'].append(std / 1e6) # Conversion en ms
        data['Seq Read']['y_err_low'].append(max(0, (avg_t - min_t) / 1e6))    #convertir en ms
        data['Seq Read']['y_err_high'].append(max(0, (max_t - avg_t) / 1e6))

        # 2. SEQUENTIAL WRITE
        # On ignore les premiers retours pour prendre avg_total (index 5), min (index 6), max (index 7)
        res_seqw = mem_stress2.sequential_write(real_size_bytes, ITERS_SEQ)
        avg_t, min_t, max_t, std = res_seqw[5], res_seqw[6], res_seqw[7], res_seqw[8]
        
        data['Seq Write']['x'].append(size_kb)
        data['Seq Write']['y'].append(avg_t / 1e6) # Conversion en ms
        data['Seq Write']['std'].append(std / 1e6)
        data['Seq Write']['y_err_low'].append(max(0, (avg_t - min_t) / 1e6))    #convertir en ms
        data['Seq Write']['y_err_high'].append(max(0, (max_t - avg_t) / 1e6))
        
        # 2. RANDOM READ
        # Retourne : ops_s, avg_ns, min_ns, max_ns, avg_total (index 4), min_total (index 5), max_total (index 6)
        res_rr = mem_stress2.random_access_test(real_size_bytes, ITERS_RAND, batch=BATCH_SIZE)
        avg_t, min_t, max_t, std = res_rr[5], res_rr[6], res_rr[7], res_rr[8]
        
        data['Rand Read']['x'].append(size_kb)
        data['Rand Read']['y'].append(avg_t / 1e6)
        data['Rand Read']['std'].append(std / 1e6)
        data['Rand Read']['y_err_low'].append(max(0, (avg_t - min_t) / 1e6))
        data['Rand Read']['y_err_high'].append(max(0, (max_t - avg_t) / 1e6))

        # 3. RANDOM WRITE
        res_rw = mem_stress2.random_write_test(real_size_bytes, ITERS_RAND, batch=BATCH_SIZE)
        avg_t, min_t, max_t, std = res_rw[5], res_rw[6], res_rw[7], res_rw[8]
        
        data['Rand Write']['x'].append(size_kb)
        data['Rand Write']['y'].append(avg_t / 1e6)
        #data['Rand Write']['y'].append(std / 1e6)
        data['Rand Write']['y_err_low'].append(max(0, (avg_t - min_t) / 1e6))
        data['Rand Write']['y_err_high'].append(max(0, (max_t - avg_t) / 1e6))

    # --- Tracé ---
    plt.figure(figsize=(12, 8))
    for label, d in data.items():
        plt.errorbar(
            d['x'], d['y'], yerr=[d['y_err_low'], d['y_err_high']], 
            label=label, color=d['c'], fmt='o', linewidth=2, capsize=4
        )

    plt.xscale('log')
    plt.yscale('log')
    plt.xticks(target_sizes_kb, [str(s) for s in target_sizes_kb], rotation=45)
    plt.xlabel('Taille du Bloc Mémoire (Ko)', fontweight='bold')
    plt.ylabel('Temps total de lecture/écriture du tableau (ms)', fontweight='bold')
    plt.title('Impact des Caches sur le temps de parcours total', fontsize=14)
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.legend()

    plt.savefig(os.path.join(output_dir, "latence_d'acces_au_tableau_entier_et_std.png"))
    plt.show()

if __name__ == "__main__":
    run_comparison()