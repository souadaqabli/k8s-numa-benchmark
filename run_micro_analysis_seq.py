import matplotlib.pyplot as plt
import mem_stress2
import numpy as np
import os

def run_comparison_sequential():
    print("=== Analyse Séquentielle : STD vs Min/Max ===")
    
    # 32 Ko = L1, 256 Ko = L2, 4 Mo+ = L3/RAM
    target_sizes_kb = [1, 2, 4, 6, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536]
    
    output_dir = "results/analyse_seq"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    data = {
        'Seq Read':   {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#1f77b4'},
        'Seq Write':  {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#d62728'},
    }
    
    ITERS_SEQ = 20000 

    for size_kb in target_sizes_kb:
        if size_kb < 1024:
            print(f"--- Benchmarking : {size_kb} Ko ---")
        else:
            print(f"--- Benchmarking : {size_kb/1024:.1f} Mo ---")
        
        real_size_bytes = int(size_kb * 1024)
        
        # 1. SEQUENTIAL READ
        # Warmup
        mem_stress2.sequential_read(real_size_bytes, 5000)
        # Mesure réelle
        res_sr = mem_stress2.sequential_read(real_size_bytes, ITERS_SEQ)
        avg, mini, maxi, std = res_sr[2] , res_sr[3], res_sr[4], res_sr[8]
        
        data['Seq Read']['x'].append(size_kb)
        data['Seq Read']['y'].append(avg)
        data['Seq Read']['std'].append(std)
        data['Seq Read']['y_err_low'].append(avg - mini) 
        data['Seq Read']['y_err_high'].append(maxi - avg)

        # 2. SEQUENTIAL WRITE
        # Warmup (Optionnel selon tes besoins, décommenté ici pour cohérence)
        mem_stress2.sequential_write(real_size_bytes, 5000)
        # mem_stress2.sequential_write(real_size_bytes, 20)
        res_sw = mem_stress2.sequential_write(real_size_bytes, ITERS_SEQ)
        avg, mini, maxi, std = res_sw[2] , res_sw[3], res_sw[4], res_sw[8]
        
        data['Seq Write']['x'].append(size_kb)
        data['Seq Write']['y'].append(avg)
        data['Seq Write']['std'].append(std)
        data['Seq Write']['y_err_low'].append(avg - mini) 
        data['Seq Write']['y_err_high'].append(maxi - avg)
        

    # --- Tracé ---
    print("\n[INFO] Génération du graphique...")
    plt.figure(figsize=(12, 8))
    
    # Légers décalages pour ne pas superposer les points bleus et rouges
    offsets = {
        'Seq Read':   0.95, 
        'Seq Write':  1.05,
    }

    for label, d in data.items():
        # Conversion en numpy array pour faciliter les opérations
        x_vals = np.array(d['x'])
        y_vals = np.array(d['y'])
        
        # Application du décalage
        shifted_x = x_vals * offsets[label]
        
        # Récupération des erreurs
        asymmetric_error = [d['y_err_low'], d['y_err_high']] # Pour Min/Max
        std_error = d['std']                                 # Pour STD

        # --- COUCHE 1 : La Moyenne et la STD (Le Signal) ---
        # On trace ceci en PREMIER (ou avec un zorder élevé) et en ÉPAIS
        plt.errorbar(
            shifted_x, y_vals, 
            yerr=std_error, 
            label=label,          # Le label pour la légende
            fmt='o',              # Point rond pour la moyenne
            color=d['c'],         
            elinewidth=3,         # <--- LIGNE ÉPAISSE pour la STD
            capsize=0,            # Pas de chapeau pour la STD (plus propre)
            markersize=6,
            alpha=0.9,
            zorder=5              # S'affiche au-dessus du reste
        )

        # --- COUCHE 2 : Le Min/Max (Le Bruit/Outliers) ---
        # On trace ceci en DEUXIÈME, en FIN et TRANSPARENT
        plt.errorbar(
            shifted_x, y_vals, 
            yerr=asymmetric_error, 
            fmt='none',           # Pas de point (déjà dessiné au-dessus)
            ecolor=d['c'],        # Même couleur
            elinewidth=1,       # <--- LIGNE FINE pour Min/Max
            capsize=4,            # Chapeaux pour bien voir les limites
            markeredgewidth=0.8,
            alpha=0.4,            # Transparence pour ne pas polluer
            zorder=4              # S'affiche en dessous
        )

    plt.xscale('log')
    plt.yscale('log')

    # Gestion des ticks X
    plt.xticks(
        ticks=target_sizes_kb, 
        labels=[str(s) for s in target_sizes_kb], 
        rotation=45
    )

    # Titres et Grille
    plt.xlabel('Taille du Bloc Mémoire (Ko)', fontsize=12, fontweight='bold')
    plt.ylabel('Latence (ns) [Point=Moy | Épais=STD | Fin=Min/Max]', fontsize=11, fontweight='bold')
    plt.title(f'Performance Séquentielle : Stabilité vs Perturbations\n({ITERS_SEQ} itérations)', fontsize=14)

    plt.grid(True, which="major", ls="-", alpha=0.6)
    plt.grid(True, which="minor", ls=":", alpha=0.3) # Grille mineure utile en log
    
    plt.legend(fontsize=11, loc='upper left')

    save_path = os.path.join(output_dir, "analyse_seq_std_warmup_20000.png")
    plt.savefig(save_path)
    print(f"[OK] Graphique sauvegardé : {save_path}")
    plt.show()

if __name__ == "__main__":
    run_comparison_sequential()