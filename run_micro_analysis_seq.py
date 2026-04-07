import matplotlib.pyplot as plt
import mem_stress3
import numpy as np
import os
import pandas as pd  
import seaborn as sns


def run_comparison_sequential():
    print("=== Sequential analysis: STD vs Min/Max ===")
    
    # 32 Ko = L1, 256 Ko = L2, 4 Mo+ = L3/RAM
    target_sizes_kb = [1, 2, 4, 6, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536,131072,  262144, 524288,  1048576] #,2097152, 3145728
    
    output_dir = "results/analyse_seq"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    data = {
        'Seq Read':   {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#1f77b4'},
        'Seq Write':  {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#d62728'},
    }
    
    ITERS_SEQ = 2000 

    for size_kb in target_sizes_kb:
        if size_kb < 1024:
            print(f"--- Benchmarking : {size_kb} Ko ---")
        else:
            print(f"--- Benchmarking : {size_kb/1024:.1f} Mo ---")
        
        real_size_bytes = int(size_kb * 1024)
        
        # 1. SEQUENTIAL READ
        # Warmup
        #mem_stress3.sequential_read(real_size_bytes, 5000)
        # Mesure réelle
        res_sr = mem_stress3.sequential_read(real_size_bytes, ITERS_SEQ)
        avg, mini, maxi, std = res_sr[2] , res_sr[3], res_sr[4], res_sr[8]
        
        data['Seq Read']['x'].append(size_kb)
        data['Seq Read']['y'].append(avg)
        data['Seq Read']['std'].append(std)
        data['Seq Read']['y_err_low'].append(avg - mini) 
        data['Seq Read']['y_err_high'].append(maxi - avg)

        # 2. SEQUENTIAL WRITE
        # Warmup (
        #mem_stress3.sequential_write(real_size_bytes, 5000)
        res_sw = mem_stress3.sequential_write(real_size_bytes, ITERS_SEQ)
        avg, mini, maxi, std = res_sw[2] , res_sw[3], res_sw[4], res_sw[8]
        
        data['Seq Write']['x'].append(size_kb)
        data['Seq Write']['y'].append(avg)
        data['Seq Write']['std'].append(std)
        data['Seq Write']['y_err_low'].append(avg - mini) 
        data['Seq Write']['y_err_high'].append(maxi - avg)


    # =================================================================
    # LINEAR REGRESSION - FITTING (SEABORN)
    # =================================================================
    print("\n[INFO] Overhead dilution analysis...")
    rows = []
    for mode in ['Seq Read', 'Seq Write']:
        for i in range(len(data[mode]['x'])):
            rows.append({
                'size_kb': data[mode]['x'][i],
                'lat_ns': data[mode]['y'][i],
                'mode': mode
            })
    df_plot = pd.DataFrame(rows)
    df_plot['inv_size'] = 1 / df_plot['size_kb']

    sns.set_theme(style="whitegrid")
    g = sns.lmplot(
        data=df_plot,
        x="inv_size", y="lat_ns", hue="mode",
        palette={'Seq Read': '#1f77b4', 'Seq Write': '#d62728'},
        height=6, aspect=1.4,
        scatter_kws={"s": 60, "edgecolor": "w", "alpha": 0.8},
        line_kws={"lw": 2}
    )
    plt.title("Global Regression : Analyse of Residual Overhead ", fontsize=14)
    plt.xlabel("1 / Size(Ko^-1)  <-- [Bigger]   [smaller] -->", fontsize=12)
    plt.ylabel("Measured Latency (ns)", fontsize=12)
    plt.ylim(0, 10) 
    plt.tight_layout()

    plt.show()


    # --- Plot---
    print("\n[INFO] GENERATING PLOTS..")
    plt.figure(figsize=(12, 8))
    
    # SHIFFTING
    offsets = {
        'Seq Read':   0.95, 
        'Seq Write':  1.05,
    }

    for label, d in data.items():
        # Conversion to numpy arrays
        x_vals = np.array(d['x'])
        y_vals = np.array(d['y'])
        
        shifted_x = x_vals * offsets[label]
        
        # capturing errors
        asymmetric_error = [d['y_err_low'], d['y_err_high']] # Pour Min/Max
        std_error = d['std']                                 # Pour STD

        # --- COUCHE 1 : Average and STD (the Signal) ---
        plt.errorbar(
            shifted_x, y_vals, 
            yerr=std_error, 
            label=label,          # Legend
            fmt='o',              # average
            color=d['c'],         
            elinewidth=3,         # STD
            capsize=0,            
            markersize=6,
            alpha=0.9,
            zorder=5             
        )

        # --- COUCHE 2 : Min/Max (Outliers) ---
        plt.errorbar(
            shifted_x, y_vals, 
            yerr=asymmetric_error, 
            fmt='none',           
            ecolor=d['c'],       
            elinewidth=1,           # tiny line for Min/Max
            capsize=4,            
            markeredgewidth=0.8,
            alpha=0.4,            
            zorder=4              
        )

    plt.xscale('log')
    #plt.yscale('log')

    # Gestion des ticks X
    plt.xticks(
        ticks=target_sizes_kb, 
        labels=[str(s) for s in target_sizes_kb], 
        rotation=45
    )
    plt.ylim(0, 10)

    # Titres et Grille
    plt.xlabel('Memory Block Size (KB)', fontsize=12, fontweight='bold')
    plt.ylabel('Latency (ns) [Point=Mean | Bold=STD | Thin=Min/Max]', fontsize=11, fontweight='bold')
    plt.title(f'Sequential Performance: Stability vs Perturbations\n({ITERS_SEQ} itérations)', fontsize=14)

    plt.grid(True, which="major", ls="-", alpha=0.6)
    plt.grid(True, which="minor", ls=":", alpha=0.3) 
    
    plt.legend(fontsize=11, loc='upper left')

    save_path = os.path.join(output_dir, "analyse_seq_moins_overhead_version_finale_eng.png")
    #save_path = os.path.join(output_dir, "analyse_seq_initiale.png")
    plt.savefig(save_path)
    print(f"[OK] Plot saved : {save_path}")
    plt.show()




if __name__ == "__main__":
    run_comparison_sequential()