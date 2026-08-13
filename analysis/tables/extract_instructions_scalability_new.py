import pandas as pd
import os
import glob
import re

def extract_last_run_totals():
    # --- AUTO-DÉTECTION DU DOSSIER ---
    chemin_sdn4 = "/home/sdnuser/sdn2_remote_data/diagnostics"
    chemin_sdn2 = "/home/sdnuser/k8s-numa-benchmark/results/diagnostics"
    
    if os.path.exists(chemin_sdn4):
        root_dir = chemin_sdn4
        print(f"[INFO] Lecture via montage distant : {root_dir}")
    elif os.path.exists(chemin_sdn2):
        root_dir = chemin_sdn2
        print(f"[INFO] Lecture locale : {root_dir}")
    else:
        root_dir = "./results/diagnostics"

    scenario_csvs = {}
    
    if not os.path.exists(root_dir):
        print(f"[ERREUR] Le dossier {root_dir} est introuvable.")
        return

    folders = [f for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]
    print(f"\n--- Analyse de {len(folders)} dossiers détectés ---")
    
    for folder in folders:
        folder_lower = folder.lower()
        
        # =========================================================
        # DÉTECTION EXPLICITE ET ROBUSTE
        # =========================================================
        
        # 1. Détection du Scénario
        if "extreme-cross" in folder_lower or "excr" in folder_lower:
            scen_type = "extreme-cross"
        elif "cross-numa" in folder_lower or "cross" in folder_lower:
            scen_type = "cross-numa"
        elif "extreme" in folder_lower or "extr" in folder_lower:
            scen_type = "extreme"
        elif "baseline" in folder_lower or "base" in folder_lower:
            scen_type = "baseline"
        elif "native-heavy" in folder_lower or "native-light" in folder_lower:
            scen_type = "native-asym"
        elif "native" in folder_lower:
            scen_type = "native"
        else:
            continue # Ignore les dossiers non reconnus

        # 2. Détection du Pattern
        if "seq" in folder_lower:
            pattern = "seq"
        elif "rand" in folder_lower:
            pattern = "rand"
        else:
            continue

        # 3. Détection du Nombre de Pods (Cores)
        if scen_type == "native-asym":
            n_cores = 6
        else:
            # Cherche -n10, -n12, -n4, etc.
            match_cores = re.search(r'-n(\d+)', folder_lower)
            n_cores = int(match_cores.group(1)) if match_cores else 4

        key = (scen_type, n_cores, pattern)

        # =========================================================
        # RECHERCHE RÉCURSIVE DES CSV
        # =========================================================
        if key not in scenario_csvs:
            scenario_csvs[key] = []
            
        folder_path = os.path.join(root_dir, folder)
        csv_files = glob.glob(os.path.join(folder_path, "**", "*.csv"), recursive=True)
        
        for csv_file in csv_files:
            scenario_csvs[key].append((csv_file, os.path.getmtime(csv_file)))

    # =========================================================
    # CALCUL ET SAUVEGARDE
    # =========================================================
    print("\n--- Début des calculs ---")
    data_rows_scale = []
    data_rows_simple = []
    
    for (scen_type, n_cores, pattern), csv_list in scenario_csvs.items():
        # Tri du plus récent au plus ancien
        csv_list.sort(key=lambda x: x[1], reverse=True)
        
        # On prend les 'n_cores' fichiers les plus récents
        latest_csvs = csv_list[:n_cores]
        total_instructions = 0
        success_reads = 0
        
        for csv_path, _ in latest_csvs:
            try:
                df = pd.read_csv(csv_path)
                if 'IPC' in df.columns and 'cycles' in df.columns:
                    pod_inst = (df['IPC'] * df['cycles']).sum()
                    total_instructions += pod_inst
                    success_reads += 1
            except Exception:
                pass
                
        if total_instructions > 0:
            print(f" [OK] {scen_type.upper():<15} | {pattern:<4} | {n_cores:2d} pods -> {total_instructions:.0f} inst. ({success_reads} fichiers lus)")
            
            # Format Scalabilité (4 colonnes) - Utile pour votre courbe de scalabilité
            data_rows_scale.append({
                'scen_type': scen_type,
                'n_cores': n_cores,
                'pattern': pattern,
                'instructions': total_instructions
            })
            
            # Format Simple pour les Bar Charts (2 colonnes)
            # On ne sauvegarde que les N=4 (ou N=16/asym) pour ne pas polluer l'autre graphique à barres
            if 'native' in scen_type:
                if scen_type == 'native-asym':
                    key_simple = f"native-asym-{pattern}"
                    data_rows_simple.append({'scenario': key_simple, 'total_instructions': total_instructions})
                elif n_cores == 16:
                    key_simple = f"native-overload-{pattern}"
                    data_rows_simple.append({'scenario': key_simple, 'total_instructions': total_instructions})
                elif n_cores == 4:
                    key_simple = f"native-{pattern}"
                    data_rows_simple.append({'scenario': key_simple, 'total_instructions': total_instructions})
            else:
                if n_cores == 4: # On limite les bare-metal à N=4 pour le fichier simple
                    key_simple = f"{scen_type}-{pattern}-work"
                    data_rows_simple.append({'scenario': key_simple, 'total_instructions': total_instructions})

    # Sauvegarde
    if data_rows_scale:
        df_scale = pd.DataFrame(data_rows_scale)
        df_scale.to_csv("total_instructions_work_scalability_new.csv", index=False)
        
    if data_rows_simple:
        df_simple = pd.DataFrame(data_rows_simple)
        df_simple.to_csv("total_instructions_work_new.csv", index=False, header=False) 
        print(f"\n[SUCCÈS] Les fichiers CSV ont été générés et mis à jour !")

# Exécution
if __name__ == "__main__":
    extract_last_run_totals()