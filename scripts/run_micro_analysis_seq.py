import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import pandas as pd
import seaborn as sns


def run_comparison_sequential():
    print("=== Sequential analysis: STD vs Min/Max ===")
    
    # 32 Ko = L1, 256 Ko = L2, 4 Mo+ = L3/RAM
    target_sizes_kb = [1, 2, 4, 6, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536,131072,  262144, 524288,  1048576] #,2097152, 3145728

    # =================================================================
    # [MODIFICATION] GESTION DYNAMIQUE DES CHEMINS
    # =================================================================
    # 1. On lit le dossier racine passé par Kubernetes (ex: /app/results/numa0_isolated)
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "numa0_isolated"

    # 2. On construit les chemins dynamiquement
    csv_path = os.path.join(base_dir, "memory_benchmark_results.csv")
    output_dir = os.path.join(base_dir, "analyse_seq")
    
    # 3. On s'assure que le dossier de sortie pour les images existe !
    os.makedirs(output_dir, exist_ok=True)
    # =================================================================
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] Inexistant file : {csv_path}")
        print("Run first script.py to generate metrics.")
        return

    print(f"[INFO] Reading data from {csv_path}...")
    df = pd.read_csv(csv_path)

    # Séparation des données Séquentielles (Read et Write)
    df_sr = df[df['pattern'] == 'sequential_read'].copy()
    df_sw = df[df['pattern'] == 'sequential_write'].copy()

    
    # Liste des tailles pour l'affichage (récupérée directement des données)
    target_sizes_kb = sorted(df_sr['size_kb'].unique())

    # =================================================================
    # LINEAR REGRESSION - FITTING (SEABORN)
    # =================================================================
    print("\n[INFO] Overhead dilution analysis...")
    
    # [MODIFICATION] Préparation des données pour Seaborn (beaucoup plus simple avec pandas)
    df_plot = df[df['pattern'].isin(['sequential_read', 'sequential_write'])].copy()
    df_plot['inv_size'] = 1 / df_plot['size_kb']
    df_plot['mode'] = df_plot['pattern'].replace({'sequential_read': 'Seq Read', 'sequential_write': 'Seq Write'})

    sns.set_theme(style="whitegrid")
    g = sns.lmplot(
        data=df_plot,
        x="inv_size", y="lat_ns", hue="mode",
        palette={'Seq Read': '#1f77b4', 'Seq Write': '#d62728'},
        height=6, aspect=1.4,
        scatter_kws={"s": 60, "edgecolor": "w", "alpha": 0.8},
        line_kws={"lw": 2}
    )
    plt.title("Global Regression : Analyse of Residual Overhead", fontsize=14)
    plt.xlabel("1 / Size(Ko^-1)  <-- [Bigger]   [smaller] -->", fontsize=12)
    plt.ylabel("Measured Latency (ns)", fontsize=12)
    plt.ylim(0, 10) 
    plt.tight_layout()

    # Optionnel : sauvegarder ce premier graphe
    plt.savefig(os.path.join(output_dir, "analyse_seq_regression.png"))
        
    # =================================================================
    # GRAPHIQUE PRINCIPAL : LATENCE VS TAILLE (MATPLOTLIB)
    # =================================================================
    print("\n[INFO] GENERATING PLOTS..")
    plt.figure(figsize=(12, 8))
    
    # SHIFTING (Décalages pour la lisibilité)
    offsets = {'Seq Read': 0.95, 'Seq Write': 1.05}
    
    # Dictionnaire de configuration pour itérer facilement
    plot_configs = [
        ('Seq Read', df_sr, '#1f77b4'),
        ('Seq Write', df_sw, '#d62728')
    ]

    for label, df_sub, color in plot_configs:
        if df_sub.empty:
            continue
            
        x_vals = df_sub['size_kb'].values
        y_vals = df_sub['lat_ns'].values
        
        shifted_x = x_vals * offsets[label]
        
        # [MODIFICATION] Calcul des barres d'erreur directement depuis les colonnes du CSV
        err_low = y_vals - df_sub['min_ns'].values
        err_high = df_sub['max_ns'].values - y_vals
        asymmetric_error = [err_low, err_high]
        
        std_error = df_sub['std_ns'].values

        # --- COUCHE 1 : Average and STD (the Signal) ---
        plt.errorbar(
            shifted_x, y_vals, 
            yerr=std_error, 
            label=label,          
            fmt='o',              
            color=color,         
            elinewidth=3,         
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
            ecolor=color,       
            elinewidth=1,           
            capsize=4,            
            markeredgewidth=0.8,
            alpha=0.4,            
            zorder=4              
        )

    plt.xscale('log')

    # Gestion des ticks X
    plt.xticks(
        ticks=target_sizes_kb, 
        labels=[str(int(s)) for s in target_sizes_kb], 
        rotation=45
    )
    plt.ylim(0, 10)

    # Titres et Grille
    plt.xlabel('Memory Block Size (KB)', fontsize=12, fontweight='bold')
    plt.ylabel('Latency (ns) [Point=Mean | Bold=STD | Thin=Min/Max]', fontsize=11, fontweight='bold')
    plt.title(f'Sequential Performance: Stability vs Perturbations\n(Source: {csv_path})', fontsize=14)

    plt.grid(True, which="major", ls="-", alpha=0.6)
    plt.grid(True, which="minor", ls=":", alpha=0.3) 
    
    plt.legend(fontsize=11, loc='upper left')

    save_path = os.path.join(output_dir, "analyse_seq_moins_overhead_version_finale_eng.png")
    plt.savefig(save_path)
    print(f"[OK] Plot saved : {save_path}")

if __name__ == "__main__":
    run_comparison_sequential()
