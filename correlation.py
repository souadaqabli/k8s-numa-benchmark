import pandas as pd
import subprocess
import re
import seaborn as sns
import matplotlib.pyplot as plt
import mem_stress2

def generate_correlation_df():
    # --- LISTE ÉQUILIBRÉE DES TAILLES ---
    sizes_kb = [
        4, 16, 28,             # L1
        48, 128, 224,          # L2
        512, 1024, 2048, 3072, # L3
        6144, 8192, 16384, 32768, 65536 # RAM
    ]
    
    data_list = []
    
    # PARAMÈTRES FIXES DU TEST
    TEST_MODE = "random_write_test" # ou "sequential_read", etc.
    BATCH_SIZE = 50000         # Doit correspondre à la valeur par défaut dans mem_stress2.py

    for size_kb in sizes_kb:
        size_bytes = size_kb * 1024
        print(f"Collecte {TEST_MODE} : {size_kb} Ko...")

        # 1. Mesure des MISSES
        # Attention : On utilise bien 'random_write' ici aussi
        if "random" in TEST_MODE:
            # Les fonctions random prennent 3 arguments (size, iters, batch)
            perf_py_cmd = f"import mem_stress2; mem_stress2.{TEST_MODE}({size_bytes}, 10000, {BATCH_SIZE})"
        else:
            # Les fonctions séquentiel ne prennent que 2 arguments (size, iters)
            perf_py_cmd = f"import mem_stress2; mem_stress2.{TEST_MODE}({size_bytes}, 10000)"

        cmd = [
            "sudo", "perf", "stat", 
            "-e", "L1-dcache-load-misses,LLC-load-misses", 
            "-x", ";", 
            "python3", "-c", perf_py_cmd
        ]   
        # Note : J'ai ajouté l'argument batch (50000) dans la commande python ci-dessus 
        # pour être sûr qu'on contrôle bien ce paramètre.
        
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        l1_misses = 0
        llc_misses = 0
        for line in proc.stderr.splitlines():
            parts = line.split(";")
            if len(parts) >= 3:
                val = int(parts[0].replace(",", ""))
                if "L1-dcache-load-misses" in parts[2]:
                    l1_misses = val
                elif "LLC-load-misses" in parts[2]:
                    llc_misses = val

        # 2. Récupération des LATENCES
        # On appelle la fonction correspondante dynamiquement ou avec des if
        if TEST_MODE == "random_write_test":
            res = mem_stress2.random_write_test(size_bytes, 10000, BATCH_SIZE)
        elif TEST_MODE == "random_access_test":
            res = mem_stress2.random_access_test(size_bytes, 10000, BATCH_SIZE)
        elif TEST_MODE == "sequential_read":
            res = mem_stress2.sequential_read(size_bytes, 10000)
        elif TEST_MODE == "sequential_write":
            res = mem_stress2.sequential_write(size_bytes, 10000)
        
        # La liste des latences brutes est toujours le dernier élément retourné
        lats_raw = res[-1] 

        # 3. Remplissage avec la CORRECTION DU DIVISEUR
        for lat_raw in lats_raw:
            
            # --- C'EST ICI QUE TOUT SE JOUE ---
            if "random" in TEST_MODE:
                # En random, lat_raw est le temps pour 'BATCH_SIZE' accès
                lat_per_elem = lat_raw / BATCH_SIZE
            else:
                # En séquentiel, lat_raw est le temps pour TOUT le tableau
                num_elements = size_bytes // 8
                lat_per_elem = lat_raw / num_elements
            # ----------------------------------
            
            data_list.append({
                'latence': lat_per_elem,
                'block_size_kb': size_kb,
                'l1_misses': l1_misses,
                'llc_misses': llc_misses
            })

    return pd.DataFrame(data_list)

df_corr = generate_correlation_df()

# --- Étape 2 : Créer le Displot Bivarié (Comme ton schéma) ---
# On utilise kind="hist" pour avoir les carrés de densité
#g = sns.displot(
    #data=df_corr, 
    #x="llc_misses",    # Axe X : Nombre de LLC misses
    #y="latence",       # Axe Y : Latence par élément
    #kind="hist",       # <--- CRUCIAL : C'est ce qui crée les "carrés" de ton dessin
    #bins=40,           # Découpe la grille en 40x40 carrés
    #cbar=True,         # Affiche la barre d'échelle de couleur (densité)
    #log_scale=(False, True), # Met l'axe Y en LOG pour voir les pics système
    #cmap="mako"        # Palette foncée (plus c'est sombre, plus il y a de points)
#)



#----------------------------------------------------------#


# 4. On configure le style pour qu'il soit propre
#sns.set_theme(style="ticks")

# 5. On crée le graphique (Histogramme 2D)
g = sns.displot(
    data=df_corr, 
    x="llc_misses",
    y="latence",
    kind="hist",
    bins=(15,40),
    #cbar=True,
    cmap="Blues",
    log_scale=(False, True),
    pmax=0.95, 
    linewidth=0.5
)

# Sauvegarde le DataFrame dans ton dossier projet
df_corr.to_csv("results/correlations/donnees_correlation_complet_randwrite.csv", index=False)
print("\nFichier 'donnees_correlation_complet_randwrite.csv' créé avec succès.")
# 3. On ajoute les labels comme sur ton schéma
g.set_axis_labels("Nombre de LLC-load-misses", "Latence par élément (ns) [Log]")
plt.title("Analyse de Densité : Impact des Cache Misses sur la Latence")

# 4. Sauvegarde pour rapport de TER
plt.savefig("results/correlations/displot_randwrite.png", dpi=300)
plt.show()

