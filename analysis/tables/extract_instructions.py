import pandas as pd
import os
import glob

def extract_total_instructions_to_csv(root_dir, output_filename="instructions_extract.csv"):
    """
    Parcourt le dossier racine, calcule les instructions (IPC * cycles)
    et sauvegarde les résultats dans un fichier CSV.
    """
    # On utilise une liste pour stocker les lignes du futur tableau
    data_rows = []

    scenario_dirs = [d for d in glob.glob(os.path.join(root_dir, "*")) if os.path.isdir(d)]

    for scenario_dir in scenario_dirs:
        scenario_name = os.path.basename(scenario_dir)
        total_scenario_instructions = 0
        
        # Cible les fichiers de la benchmark suite
        perf_files = glob.glob(os.path.join(scenario_dir, "*", "memory_benchmark_*.csv"))
        
        if not perf_files:
            continue
            
        for file in perf_files:
            try:
                df = pd.read_csv(file)
                if 'IPC' in df.columns and 'cycles' in df.columns:
                    df['instructions_exec'] = df['IPC'] * df['cycles']
                    total_scenario_instructions += df['instructions_exec'].sum()
            except Exception as e:
                print(f"Erreur de lecture sur {file}: {e}")
        
        if total_scenario_instructions > 0:
            # On ajoute le résultat pour ce scénario dans notre liste
            data_rows.append({
                'scenario': scenario_name,
                'total_instructions': total_scenario_instructions
            })

    # Si on a trouvé des données, on crée un DataFrame et on l'exporte en CSV
    if data_rows:
        df_results = pd.DataFrame(data_rows)
        
        # On trie par nom de scénario pour que ce soit propre
        df_results = df_results.sort_values(by='scenario')
        
        # Sauvegarde dans le fichier
        df_results.to_csv(output_filename, index=False)
        print(f"Extraction terminée ! Les données ont été sauvegardées dans : {output_filename}")
        
        # Petit affichage de contrôle
        print("\nAperçu du fichier généré :")
        print(df_results.to_string(index=False))
    else:
        print("Aucune donnée d'instruction n'a pu être extraite.")

# ==========================================
# UTILISATION
# ==========================================

dossier_cible = "./results/RESULTS_WORK"  # <-- Mettez ici le chemin vers votre dossier de résultats TIME
fichier_sortie = "total_instructions_work.csv"

print(f"Lancement de l'extraction sur : {dossier_cible}...\n")
extract_total_instructions_to_csv(dossier_cible, fichier_sortie)