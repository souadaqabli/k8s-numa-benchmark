import matplotlib.pyplot as plt
import mem_stress3
import numpy as np
import os

def run_comparison_random():
    print("=== Analyse Aleatoire : STD vs Min/Max ===")
    
    # 32 Ko = L1, 256 Ko = L2, 4 Mo+ = L3/RAM
    target_sizes_kb = [1, 2, 4, 6, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536, 131072,  262144, 524288,  1048576]
    
    output_dir = "results/analyse_rand"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    data = {
        'Rand Read':   {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#ff7f0e'},
        'Rand Write':  {'x': [], 'y': [], 'std': [], 'y_err_low': [], 'y_err_high': [], 'c': '#2ca02c'},
    }
    
    ITERS_RAND = 20000 
    BATCH_SIZE = 20000

    for size_kb in target_sizes_kb:
        if size_kb < 1024:
            print(f"--- Benchmarking : {size_kb} Ko ---")
        else:
            print(f"--- Benchmarking : {size_kb/1024:.1f} Mo ---")
        
        real_size_bytes = int(size_kb * 1024)
        
        # 1. SEQUENTIAL READ
        res_rr = mem_stress3.random_access_test(real_size_bytes, ITERS_RAND, batch=BATCH_SIZE)
        avg, mini, maxi, std = res_rr[2] , res_rr[3], res_rr[4], res_rr[8]
        
        data['Rand Read']['x'].append(size_kb)
        data['Rand Read']['y'].append(avg)
        data['Rand Read']['std'].append(std)
        data['Rand Read']['y_err_low'].append(avg - mini)
        data['Rand Read']['y_err_high'].append(maxi - avg)

        # 3. RANDOM WRITE
        #_,_, avg, mini, maxi, _, _, _, std = mem_stress3.random_write_test(real_size_bytes, ITERS_RAND, batch=BATCH_SIZE)
        res_rw = mem_stress3.random_access_test(real_size_bytes, ITERS_RAND, batch=BATCH_SIZE)
        avg, mini, maxi, std = res_rw[2] , res_rw[3], res_rw[4], res_rw[8]
        
        data['Rand Write']['x'].append(size_kb)
        data['Rand Write']['y'].append(avg)
        data['Rand Write']['std'].append(std)
        data['Rand Write']['y_err_low'].append(avg - mini)
        data['Rand Write']['y_err_high'].append(maxi - avg)


    # --- Tracé ---
    print("\n[INFO] Génération du graphique...")
    plt.figure(figsize=(12, 8))
    
    # Légers décalages pour ne pas superposer les points bleus et rouges
    offsets = {
        'Rand Read':   0.95, 
        'Rand Write':  1.05,
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
    plt.title(f'Performance Aleatoire : Stabilité vs Perturbations\n({ITERS_RAND} itérations)', fontsize=14)

    plt.grid(True, which="major", ls="-", alpha=0.6)
    plt.grid(True, which="minor", ls=":", alpha=0.3) # Grille mineure utile en log
    
    plt.legend(fontsize=11, loc='upper left')

    save_path = os.path.join(output_dir, "analyse_rand_std_correcte_20000_Version_finale.png")
    plt.savefig(save_path)
    print(f"[OK] Graphique sauvegardé : {save_path}")
    plt.show()

if __name__ == "__main__":
    run_comparison_random()