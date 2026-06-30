import pandas as pd
import os
import glob
import re

def extract_last_run_totals(root_dir, output_filename="total_instructions_work_scalability.csv"):
    mapping = {
        'base': 'baseline', 'baseline': 'baseline',
        'extr': 'extreme', 'extreme': 'extreme',
        'cross': 'cross-numa', 'cross-numa': 'cross-numa',
        'excr': 'extreme-cross', 'extreme-cross': 'extreme-cross'
    }
    
    # Dictionary to store ALL CSV files found per scenario
    scenario_csvs = {}
    
    folders = [f for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]
    
    for folder in folders:
        folder_lower = folder.lower()
        
        # =========================================================
        # 1. TRAITEMENT SPÉCIAL : SCÉNARIOS ASYMÉTRIQUES (Heavy/Light)
        # =========================================================
        if "native-heavy" in folder_lower or "native-light" in folder_lower:
            # On force le nom du scénario global et le nombre total de cœurs
            scen_type = 'native-asym'
            n_cores = 6
            pattern = 'seq' if 'seq' in folder_lower else 'rand'
            
            key = (scen_type, n_cores, pattern)
            
        # =========================================================
        # 2. TRAITEMENT CLASSIQUE : Regex pour les autres dossiers
        # =========================================================
        else:
            # Cherche un format du type: [nom_scenario]-n[chiffre]...-[seq/rand]
            match = re.search(r'(?P<scen>.*?)-n(?P<cores>\d+)(?:-numa\d+)?(?:-.*?)?-(?P<pat>seq|rand)', folder_lower)
            
            if not match:
                # Essai d'une regex plus courte au cas où (ex: native-n4-seq)
                match = re.search(r'(?P<scen>.*?)-n(?P<cores>\d+)-(?P<pat>seq|rand)', folder_lower)
            
            if not match: 
                # Si le dossier ne correspond toujours pas, on l'ignore silencieusement
                # sauf si c'est un dossier important
                if "native" in folder_lower or "bench" in folder_lower:
                    print(f"[ATTENTION] Format de dossier ignoré : {folder}")
                continue
                
            scen_raw = match.group('scen').replace('bench-', '') # Nettoie le prefixe 'bench-' si présent
            n_cores = int(match.group('cores'))
            pattern = match.group('pat')
            
            scen_type = mapping.get(scen_raw, scen_raw)
            key = (scen_type, n_cores, pattern)
            
        # =========================================================
        # RECHERCHE RÉCURSIVE DES FICHIERS CSV
        # =========================================================
        if key not in scenario_csvs:
            scenario_csvs[key] = []
            
        folder_path = os.path.join(root_dir, folder)
        # On fouille de fond en comble (**) pour trouver les CSV
        csv_files = glob.glob(os.path.join(folder_path, "**", "*.csv"), recursive=True)
        
        if not csv_files and ("heavy" in folder_lower or "light" in folder_lower):
            print(f"[ATTENTION] Dossier trouvé mais VIDE : {folder}")
        
        # Sauvegarde le chemin exact ET la date de modification
        for csv_file in csv_files:
            scenario_csvs[key].append((csv_file, os.path.getmtime(csv_file)))
            
    data_rows = []
    
    # =========================================================
    # CALCUL ET SAUVEGARDE
    # =========================================================
    for (scen_type, n_cores, pattern), csv_list in scenario_csvs.items():
        # Trie TOUS les CSV du plus récent au plus ancien
        csv_list.sort(key=lambda x: x[1], reverse=True)
        
        # On garde UNIQUEMENT les 'n_cores' fichiers les plus récents
        # Ex: Pour native-asym, il prendra les 6 CSV les plus récents générés par heavy et light combinés
        latest_csvs = csv_list[:n_cores]
        
        total_instructions = 0
        
        # Lit ces N fichiers et fait la somme
        for csv_path, _ in latest_csvs:
            try:
                df = pd.read_csv(csv_path)
                if 'IPC' in df.columns and 'cycles' in df.columns:
                    pod_inst = (df['IPC'] * df['cycles']).sum()
                    total_instructions += pod_inst
            except Exception as e:
                print(f"[ERROR] Impossible de lire {csv_path} : {e}")
                pass
                
        # On n'ajoute la ligne que si on a bien trouvé des instructions
        if total_instructions > 0:
            data_rows.append({
                'scen_type': scen_type,
                'n_cores': n_cores,
                'pattern': pattern,
                'instructions': total_instructions
            })

    # Sauvegarde du résultat
    df_results = pd.DataFrame(data_rows)
    df_results.to_csv(output_filename, index=False)
    print(f"[SUCCESS] Extraction terminée. {len(df_results)} lignes générées dans {output_filename}.")

# Exécution
extract_last_run_totals("/home/sdnuser/sdn2_remote_data", "total_instructions_work_scalability.csv")