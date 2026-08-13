"""
Génère un tableau récapitulatif (moyenne, écart-type, CV%) de puissance et durée
pour chaque combinaison (scenario, pattern, cores), à partir des fichiers RAPL bruts.

Gère deux fichiers sources qui peuvent chacun contenir un MÉLANGE de deux formats
de lignes différents (comme rapl_global_results_config1_n4.csv, qui contient à la
fois les 4 scénarios Config A/B/C et les lignes native/native-overload) :

  Format A : "scenario_name,run_id,duration_s,total_uj,pkg0,pkg1,dram0,dram1"
             ex: baseline-seq-work,run1,78,4414661879,2192734534,...
             (utilisé pour baseline/extreme/cross-numa/extreme-cross)

  Format B : "pattern,cores,scenario,duration_s,total_uj,pkg0,pkg1,dram0,dram1"
             ex: seq,N4,native,79,4334034962,2151614820,...
             (utilisé pour native/native-overload)

Le format est détecté automatiquement ligne par ligne (pas besoin de séparer les
fichiers en amont).

Usage :
    python3 generate_summary_table.py
"""

import pandas as pd
import numpy as np
import os
import csv

# ============================================================
# CONFIGURATION - à adapter à tes chemins réels
# ============================================================

INPUT_FILES = [
    "results/RAPL/rapl_global_results_config1_n4.csv",
    "results/RAPL/scalability_energy_results_complete.csv",
]

OUTPUT_CSV = "summary_table.csv"
OUTPUT_MD = "summary_table.md"
OUTPUT_REPORT_CSV = "summary_table_report.csv"
OUTPUT_REPORT_MD = "summary_table_report.md"

# Seuil de CV% au-delà duquel un combo est flagué comme instable
CV_THRESHOLD = 8.0

# ============================================================
# PARSING LIGNE PAR LIGNE AVEC DÉTECTION AUTOMATIQUE DE FORMAT
# ============================================================

def parse_line(row):
    """Détecte le format d'une ligne CSV brute (liste de champs) et retourne
    un dict normalisé {pattern, cores, scenario, duration_s, pkg0_uj, pkg1_uj,
    dram0_uj, dram1_uj}, ou None si la ligne est un en-tête ou illisible."""

    if not row or len(row) < 8:
        return None

    first = row[0].strip().lower()

    # Ignorer les lignes d'en-tête
    if first in ('scenario', 'pattern'):
        return None

    # --- FORMAT B : pattern,cores,scenario,duration,total,pkg0,pkg1,dram0,dram1 ---
    if first in ('seq', 'rand') and len(row) >= 9:
        try:
            return {
                'pattern': row[0].strip().lower(),
                'cores': row[1].strip().upper(),
                'scenario': row[2].strip().lower(),
                'duration_s': float(row[3]),
                'pkg0_uj': float(row[5]),
                'pkg1_uj': float(row[6]),
                'dram0_uj': float(row[7]),
                'dram1_uj': float(row[8]),
            }
        except (ValueError, IndexError):
            return None

    # --- FORMAT A : scenario_name[-work|-time][,run_id],duration,total,pkg0,pkg1,dram0,dram1 ---
    # 7 champs SANS run_id (name,duration,total,pkg0,pkg1,dram0,dram1)
    # 8 champs AVEC run_id (name,run_id,duration,total,pkg0,pkg1,dram0,dram1)
    if 'seq' in first or 'rand' in first:
        name = first
        pattern = 'rand' if 'rand' in name else 'seq'

        if 'extreme-cross' in name:
            scenario = 'extreme-cross'
        elif 'cross-numa' in name:
            scenario = 'cross-numa'
        elif 'extreme' in name:
            scenario = 'extreme'
        elif 'baseline' in name:
            scenario = 'baseline'
        else:
            return None

        # Le 2e champ est un run_id s'il n'est pas un nombre (ex: 'run1' vs '78')
        has_run_id = not row[1].strip().replace('.', '', 1).isdigit()
        offset = 1 if has_run_id else 0
        try:
            return {
                'pattern': pattern,
                'cores': None,  # déterminé plus tard (pas de colonne 'cores' dans ce format)
                'scenario': scenario,
                'duration_s': float(row[1 + offset]),
                'pkg0_uj': float(row[3 + offset]),
                'pkg1_uj': float(row[4 + offset]),
                'dram0_uj': float(row[5 + offset]),
                'dram1_uj': float(row[6 + offset]),
            }
        except (ValueError, IndexError):
            return None

    return None


def load_file(path, default_cores=None):
    """Charge un fichier et retourne une liste de dicts normalisés.
    `default_cores` : palier N à assigner aux lignes Format A qui n'ont pas de
    colonne 'cores' explicite (ex: 'N4' pour un fichier dédié à ce seul palier)."""
    records = []
    with open(path, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            parsed = parse_line(row)
            if parsed is None:
                continue
            if parsed['cores'] is None:
                if default_cores is None:
                    print(f"[WARN] Ligne sans 'cores' et sans default_cores fourni, ignorée : {row}")
                    continue
                parsed['cores'] = default_cores
            records.append(parsed)
    return records


def load_all_sources():
    all_records = []
    for path in INPUT_FILES:
        if not os.path.exists(path):
            print(f"[WARN] Fichier introuvable, ignoré : {path}")
            continue
        # Pour les lignes Format A (sans colonne cores), on assigne N4 par défaut :
        # c'est le cas de rapl_global_results_config1_n4.csv, dédié au palier N4.
        # Si un autre fichier "config1_nX" existe pour un autre palier, ajuste ici.
        default_cores = 'N4' if 'config1_n4' in path else None
        all_records.extend(load_file(path, default_cores=default_cores))

    if not all_records:
        raise ValueError("Aucune donnée valide trouvée. Vérifie INPUT_FILES en haut du script.")

    df = pd.DataFrame(all_records)

    # --- DÉDUPLICATION ---
    # Si un même run existe dans deux fichiers différents (mêmes valeurs exactes),
    # on ne le garde qu'une fois.
    before = len(df)
    df = df.drop_duplicates(
        subset=['pattern', 'cores', 'scenario', 'duration_s', 'pkg0_uj', 'pkg1_uj', 'dram0_uj', 'dram1_uj']
    )
    after = len(df)
    if before != after:
        print(f"[INFO] {before - after} ligne(s) dupliquée(s) retirée(s) (même run présent dans plusieurs fichiers).")

    return df


# ============================================================
# CALCUL DE LA PUISSANCE (toujours PKG+DRAM, jamais total_uj brut)
# ============================================================

def compute_power(df):
    df = df.copy()
    df['power_w'] = (df['pkg0_uj'] + df['pkg1_uj'] + df['dram0_uj'] + df['dram1_uj']) / df['duration_s'] / 1e6
    return df


# ============================================================
# AGRÉGATION : moyenne, écart-type, CV% par combo
# ============================================================

def aggregate(group):
    n = len(group)
    p_mean = group['power_w'].mean()
    p_std = group['power_w'].std(ddof=1) if n > 1 else np.nan
    p_cv = 100 * p_std / p_mean if n > 1 else np.nan

    d_mean = group['duration_s'].mean()
    d_std = group['duration_s'].std(ddof=1) if n > 1 else np.nan
    d_cv = 100 * d_std / d_mean if n > 1 else np.nan

    flag = '⚠️' if (n > 1 and (p_cv > CV_THRESHOLD or d_cv > CV_THRESHOLD)) else ''

    return pd.Series({
        'n_runs': n,
        'power_mean_W': round(p_mean, 2),
        'power_std_W': round(p_std, 2) if n > 1 else None,
        'power_cv_%': round(p_cv, 2) if n > 1 else None,
        'duration_mean_s': round(d_mean, 1),
        'duration_std_s': round(d_std, 2) if n > 1 else None,
        'duration_cv_%': round(d_cv, 2) if n > 1 else None,
        'flag': flag,
    })


def build_summary_table(df):
    table = df.groupby(['scenario', 'pattern', 'cores']).apply(aggregate).reset_index()

    scenario_order = ['baseline', 'extreme', 'cross-numa', 'extreme-cross', 'native']
    cores_order = ['N4', 'N6', 'N8', 'N10', 'N12', 'N16']
    table['scenario'] = pd.Categorical(table['scenario'], categories=scenario_order, ordered=True)
    table['cores'] = pd.Categorical(table['cores'], categories=cores_order, ordered=True)
    table = table.sort_values(['scenario', 'pattern', 'cores']).reset_index(drop=True)

    return table


def build_report_table(summary):
    """Construit une version 'prête pour le rapport' : puissance et durée au
    format 'moyenne ± écart-type' dans une seule cellule (ex: '68.96 ± 3.58 W'),
    plus le nombre de runs entre parenthèses pour la traçabilité."""

    def fmt(mean, std, unit, n):
        if n == 1 or pd.isna(std):
            return f"{mean:.2f} {unit} (n=1)"
        return f"{mean:.2f} ± {std:.2f} {unit} (n={n})"

    report = pd.DataFrame({
        'Scénario': summary['scenario'].astype(str).str.capitalize(),
        'Pattern': summary['pattern'].astype(str),
        'N': summary['cores'].astype(str),
        'Puissance': summary.apply(lambda r: fmt(r['power_mean_W'], r['power_std_W'], 'W', r['n_runs']), axis=1),
        'Durée': summary.apply(lambda r: fmt(r['duration_mean_s'], r['duration_std_s'], 's', r['n_runs']), axis=1),
    })
    return report


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    df_raw = load_all_sources()
    df_raw = compute_power(df_raw)

    summary = build_summary_table(df_raw)
    report = build_report_table(summary)

    summary.to_csv(OUTPUT_CSV, index=False)
    with open(OUTPUT_MD, 'w') as f:
        f.write(summary.to_markdown(index=False))

    report.to_csv(OUTPUT_REPORT_CSV, index=False)
    with open(OUTPUT_REPORT_MD, 'w') as f:
        f.write(report.to_markdown(index=False))

    print(f"[SUCCESS] Tableau détaillé : {OUTPUT_CSV} / {OUTPUT_MD}")
    print(f"[SUCCESS] Tableau rapport (moyenne ± std) : {OUTPUT_REPORT_CSV} / {OUTPUT_REPORT_MD}")
    print(f"Combos flagués (CV% > {CV_THRESHOLD}%) : {(summary['flag'] == '⚠️').sum()} / {len(summary)}")
    print()
    print(report.to_string(index=False))