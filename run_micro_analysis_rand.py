import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd  

def run_comparison_random():
    print("=== Analysis of random mode : STD vs Min/Max (Data Visualization) ===")
    
    POD_ID = os.environ.get("POD_ID", "local")
    
    csv_path = f"results/{POD_ID}/perf/seq/memory_benchmark_results_full_seq.csv"
    output_dir = f"results/{POD_ID}/analyse_rand"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.exists(csv_path):
        print(f"[ERROR] Inexistant file : {csv_path}")
        print("First run script.py to generate metrics.")
        return

    print(f"[INFO] Reading data from {csv_path}...")
    df = pd.read_csv(csv_path)

    # Filtrage strict pour ne garder que les tests Random
    df_rr = df[df['pattern'] == 'random_read'].copy()
    df_rw = df[df['pattern'] == 'random_write'].copy()

    # Liste des tailles pour l'affichage (récupérée directement des données)
    target_sizes_kb = sorted(df_rr['size_kb'].unique())

    # --- Tracé ---
    print("\n[INFO] Generating the plot...")
    plt.figure(figsize=(12, 8))
    
    # Légers décalages pour ne pas superposer les points (Read à gauche, Write à droite)
    offsets = {'Rand Read': 0.95, 'Rand Write': 1.05}

    # Configuration simplifiée pour itérer
    plot_configs = [
        ('Rand Read', df_rr, '#ff7f0e'), 
        ('Rand Write', df_rw, '#2ca02c')  
    ]

    for label, df_sub, color in plot_configs:
        if df_sub.empty:
            continue
            
        x_vals = df_sub['size_kb'].values
        y_vals = df_sub['lat_ns'].values
        
        # Application du décalage
        shifted_x = x_vals * offsets[label]
        
        # Récupération des erreurs directement depuis les colonnes du DataFrame
        err_low = y_vals - df_sub['min_ns'].values
        err_high = df_sub['max_ns'].values - y_vals
        asymmetric_error = [err_low, err_high] # Pour Min/Max
        
        std_error = df_sub['std_ns'].values    # Pour STD

        # --- COUCHE 1 : La Moyenne et la STD (Le Signal) ---
        plt.errorbar(
            shifted_x, y_vals, 
            yerr=std_error, 
            label=label,          
            fmt='o',              
            color=color,         
            elinewidth=3,         # LIGNE ÉPAISSE pour la STD
            capsize=0,            
            markersize=6,
            alpha=0.9,
            zorder=5              
        )

        # --- COUCHE 2 : Le Min/Max (Le Bruit/Outliers) ---
        plt.errorbar(
            shifted_x, y_vals, 
            yerr=asymmetric_error, 
            fmt='none',           
            ecolor=color,        
            elinewidth=1,         # LIGNE FINE pour Min/Max
            capsize=4,            
            markeredgewidth=0.8,
            alpha=0.4,            
            zorder=4              
        )

    plt.xscale('log')
    plt.yscale('log')

    # Gestion des ticks X
    plt.xticks(
        ticks=target_sizes_kb, 
        labels=[str(int(s)) for s in target_sizes_kb], 
        rotation=45
    )

    # Titres et Grille
    plt.xlabel('Size of memory array (Ko)', fontsize=12, fontweight='bold')
    plt.ylabel('Latence (ns) [Point=Moy | Épais=STD | Fin=Min/Max]', fontsize=11, fontweight='bold')
    
    # Le titre indique a source du CSV pour la traçabilité
    plt.title(f'Performance of Random test : Stability vs Perturbations\n(Source: {csv_path})', fontsize=14)

    plt.grid(True, which="major", ls="-", alpha=0.6)
    plt.grid(True, which="minor", ls=":", alpha=0.3) 
    
    plt.legend(fontsize=11, loc='upper left')

    save_path = os.path.join(output_dir, "analyse_rand_std_correcte_Version_finale.png")
    plt.savefig(save_path)
    print(f"[OK] Graph saved : {save_path}")
    plt.show()

if __name__ == "__main__":
    run_comparison_random()