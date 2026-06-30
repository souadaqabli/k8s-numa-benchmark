import pandas as pd
import glob
import os

def extraire_metriques_microarchitecturales(chemin_dossier_scenario):
    perf_files = glob.glob(os.path.join(chemin_dossier_scenario, "**", "memory_benchmark_*.csv"), recursive=True)
    
    if not perf_files:
        return None
        
    total_cycles = 0
    total_instructions_estimees = 0
    total_llc_misses = 0
    
    for file in perf_files:
        try:
            df = pd.read_csv(file)
            
            # Reconstruction des volumes
            if 'IPC' in df.columns and 'cycles' in df.columns:
                total_cycles += df['cycles'].sum()
                total_instructions_estimees += (df['IPC'] * df['cycles']).sum()
            
            # Extraction du Last Level Cache (L3)
            if 'LLC_misses' in df.columns:
                total_llc_misses += df['LLC_misses'].sum()
                
        except Exception as e:
            print(f"[parser_perf] Erreur sur le fichier {file} : {e}")

    # Calcul de l'IPC
    ipc_moyen = total_instructions_estimees / total_cycles if total_cycles > 0 else 0
    
    # Calcul du MPKI (Misses Per Kilo Instruction) - La métrique académique !
    llc_mpki = (total_llc_misses / total_instructions_estimees * 1000) if total_instructions_estimees > 0 else 0

    return {
        'ipc': round(ipc_moyen, 3),
        'llc_mpki': round(llc_mpki, 2)
    }