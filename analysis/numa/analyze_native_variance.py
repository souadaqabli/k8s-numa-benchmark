#!/usr/bin/env python3
import pandas as pd
import os
import glob
import sys
import re

def extract_scenario_from_path(path):
    """
    Déduit le scénario du nom du dossier.
    Ex: 'native-n4-seq' → (seq, 4, native)
        'native-n12-rand' → (rand, 12, native)
    """
    basename = os.path.basename(path.rstrip('/'))
    match = re.match(r'native-n(\d+)-(seq|rand)', basename)
    if match:
        return match.group(2), int(match.group(1)), 'native'
    print(f"ERREUR: Le dossier '{basename}' ne suit pas le format 'native-N<chiffre>-<seq|rand>'")
    sys.exit(1)

def find_energy(master_csv, pattern, n_cores, scenario_type):
    """
    Lit le CSV maître et trouve l'énergie du scénario correspondant.
    """
    df = pd.read_csv(master_csv)
    
    # Chercher la ligne exacte
    row = df[(df['pattern'] == pattern) & 
             (df['cores'] == f'N{n_cores}') & 
             (df['scenario'] == scenario_type)]
    
    if row.empty:
        print(f"ERREUR: Ligne non trouvée dans {master_csv}")
        print(f"  Recherche: pattern={pattern}, cores=N{n_cores}, scenario={scenario_type}")
        print(f"  Scénarios disponibles: {df['scenario'].unique().tolist()}")
        sys.exit(1)
    
    # Calculer le VRAI total (PKG0+PKG1+DRAM0+DRAM1)
    r = row.iloc[0]
    energy_j = (r['pkg0_uj'] + r['pkg1_uj'] + r['dram0_uj'] + r['dram1_uj']) / 1e6
    
    return energy_j, r['duration_s']

def analyze(pods_dir, master_csv):
    # 1. Déduire le scénario du nom du dossier
    pattern, n, scen_type = extract_scenario_from_path(pods_dir)
    
    # 2. Lire l'énergie automatiquement depuis le CSV maître
    energy_j, duration_s = find_energy(master_csv, pattern, n, scen_type)
    
    print(f"\n{'='*70}")
    print(f"ANALYSE : {os.path.basename(pods_dir)}")
    print(f"{'='*70}")
    print(f"Pattern détecté : {pattern}")
    print(f"Nombre de pods  : {n}")
    print(f"Type            : {scen_type}")
    print(f"Énergie (RAPL)  : {energy_j:.0f} J")
    print(f"Durée           : {duration_s} s")
    print(f"Puissance moy   : {energy_j/duration_s:.1f} W")
    
    # 3. Trouver les CSV perf des pods
    csv_pattern = os.path.join(pods_dir, "**", "memory_benchmark_*.csv")
    files = glob.glob(csv_pattern, recursive=True)
    
    if not files:
        print(f"\nERREUR: Aucun CSV trouvé dans {pods_dir}")
        sys.exit(1)
    
    print(f"Pods trouvés    : {len(files)}")
    
    # 4. Lire chaque pod
    pods = []
    for f in sorted(files):
        pod_name = os.path.basename(os.path.dirname(f))
        df = pd.read_csv(f)
        
        total_cycles = df['cycles'].sum()
        total_inst = (df['IPC'] * df['cycles']).sum()
        ipc = total_inst / total_cycles if total_cycles > 0 else 0
        
        pods.append({
            'pod': pod_name,
            'instructions': total_inst,
            'ipc': ipc
        })
    
    df_pods = pd.DataFrame(pods)
    
    # 5. Calculs
    total_instructions = df_pods['instructions'].sum()
    nj_mean = (energy_j * 1e9) / total_instructions
    
    mean_ipc = df_pods['ipc'].mean()
    df_pods['nj_inst'] = df_pods['ipc'].apply(lambda x: nj_mean * (mean_ipc / x) if x > 0 else 0)
    
    cv_ipc = (df_pods['ipc'].std() / mean_ipc) * 100
    cv_nj = (df_pods['nj_inst'].std() / df_pods['nj_inst'].mean()) * 100
    ratio = df_pods['nj_inst'].max() / df_pods['nj_inst'].min()
    
    # 6. Affichage
    print(f"\n{'Pod':<45} {'IPC':>8} {'Instructions':>14} {'nJ/inst':>10}")
    print("-" * 70)
    for _, row in df_pods.iterrows():
        print(f"{row['pod']:<45} {row['ipc']:>8.3f} {row['instructions']:>14.2e} {row['nj_inst']:>10.2f}")
    
    print(f"\n{'='*70}")
    print(f"STATISTIQUES")
    print(f"{'='*70}")
    print(f"nJ/inst moyen (scénario)  : {nj_mean:.2f}")
    print(f"IPC moyen                 : {mean_ipc:.3f}")
    print(f"IPC écart-type            : {df_pods['ipc'].std():.3f}")
    print(f"IPC CV (variance %)       : {cv_ipc:.1f}%")
    print(f"nJ/inst min / max         : {df_pods['nj_inst'].min():.2f} / {df_pods['nj_inst'].max():.2f}")
    print(f"Ratio max/min             : {ratio:.2f}x")
    print(f"nJ/inst CV (variance %)   : {cv_nj:.1f}%")
    
    print(f"\n{'='*70}")
    print(f"INTERPRÉTATION")
    print(f"{'='*70}")
    if cv_ipc < 5:
        print("→ Variance FAIBLE : le scheduler a fait un placement homogène.")
        print("  Tous les pods ont des ressources équivalentes.")
    elif cv_ipc < 15:
        print("→ Variance MODÉRÉE : certains pods sont moins efficaces.")
        print("  Cause probable : HyperThreading ou NUMA suboptimal.")
    else:
        print("→ Variance ÉLEVÉE : placement chaotique, forte inégalité.")
        print("  Le scheduler a créé des conditions très différentes entre pods.")

# === UTILISATION ===
if len(sys.argv) != 3:
    print("Usage: python3 analyze_variance_auto.py <dossier_pods> <fichier_energie_master.csv>")
    print("")
    print("Exemples:")
    print("  python3 analyze_variance_auto.py /home/sdnuser/sdn2_remote_data/native-n4-seq ./results/RAPL/rapl_native_results.csv")
    print("  python3 analyze_variance_auto.py /home/sdnuser/sdn2_remote_data/native-n12-rand ./results/RAPL/rapl_native_results.csv")
    sys.exit(1)

pods_dir = sys.argv[1]
master_csv = sys.argv[2]

if not os.path.exists(pods_dir):
    print(f"ERREUR: Le dossier '{pods_dir}' n'existe pas.")
    sys.exit(1)

if not os.path.exists(master_csv):
    print(f"ERREUR: Le fichier '{master_csv}' n'existe pas.")
    sys.exit(1)

analyze(pods_dir, master_csv)