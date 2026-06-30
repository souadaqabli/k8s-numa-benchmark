#!/usr/bin/env python3
"""
parse_numastat.py
-----------------
Lit les snapshots numastat capturés par run_overload_campaign.sh
et produit:
  1. Un tableau comparatif numa_hit vs numa_miss par timestamp
  2. Un calcul du taux de cross-NUMA (numa_miss / total)
  3. Un graphe d'évolution du taux cross-NUMA pendant le job

Usage:
  python3 analysis/parse_numastat.py --dir results/numa_monitoring/overload-n16-seq/run1
  python3 analysis/parse_numastat.py --dir results/numa_monitoring/overload-n16-seq/  --all-runs
"""

import os
import re
import argparse
import glob
import pandas as pd
import matplotlib.pyplot as plt

# Ordre chronologique des snapshots
SNAPSHOT_ORDER = ["T_BEFORE", "T0_start", "T1_mid", "T2_late", "T3_end"]


def parse_numastat_system(filepath):
    """Parse un fichier numastat (sortie de 'sudo numastat' sans arguments)."""
    metrics = {}
    if not os.path.exists(filepath):
        return metrics

    with open(filepath) as f:
        lines = f.readlines()

    # Format numastat :
    # numa_hit       123456       654321
    # numa_miss        4567         8901
    # numa_foreign     8901         4567
    # interleave_hit    123          456
    # local_node    120000       640000
    # other_node      3456         9876
    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            key = parts[0]
            try:
                node0 = int(parts[1])
                node1 = int(parts[2])
                metrics[key] = {'node0': node0, 'node1': node1,
                                 'total': node0 + node1}
            except ValueError:
                pass
    return metrics


def parse_numastat_pids(filepath):
    """
    Parse 'sudo numastat -p <pids>' — donne local vs remote par processus.
    Retourne {'local': X, 'remote': Y} en MB.
    """
    result = {'local_mb': 0.0, 'remote_mb': 0.0}
    if not os.path.exists(filepath):
        return result

    with open(filepath) as f:
        content = f.read()

    # Les totaux sont dans les lignes "Total" ou "Per-node process memory usage"
    # On cherche la ligne "Total" dans le tableau récapitulatif
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Total"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    # Format: Total  <node0_MB>  <node1_MB>  [other nodes]
                    result['local_mb'] = float(parts[1])
                    result['remote_mb'] = float(parts[2])
                except (ValueError, IndexError):
                    pass
    return result


def cross_numa_rate(metrics):
    """Calcule le taux de cross-NUMA = numa_miss / (numa_hit + numa_miss)."""
    if 'numa_hit' not in metrics or 'numa_miss' not in metrics:
        return None
    total_accesses = metrics['numa_hit']['total'] + metrics['numa_miss']['total']
    if total_accesses == 0:
        return 0.0
    return metrics['numa_miss']['total'] / total_accesses * 100


def analyze_run(run_dir, run_label=""):
    """Analyse tous les snapshots d'un run et retourne un DataFrame."""
    rows = []

    for tag in SNAPSHOT_ORDER:
        sys_file = os.path.join(run_dir, f"numastat_system_{tag}.txt")
        pid_file = os.path.join(run_dir, f"numastat_pids_{tag}.txt")
        aff_file = os.path.join(run_dir, f"cpu_affinity_{tag}.txt")
        perf_file = os.path.join(run_dir, f"perf_numa_{tag}.txt")

        sys_metrics = parse_numastat_system(sys_file)
        pid_metrics = parse_numastat_pids(pid_file)

        if not sys_metrics:
            continue

        rate = cross_numa_rate(sys_metrics)
        numa_hit = sys_metrics.get('numa_hit', {}).get('total', 0)
        numa_miss = sys_metrics.get('numa_miss', {}).get('total', 0)
        other_node = sys_metrics.get('other_node', {}).get('total', 0)
        local_node = sys_metrics.get('local_node', {}).get('total', 0)

        # Perf NUMA events
        local_dram = remote_dram = None
        if os.path.exists(perf_file):
            with open(perf_file) as f:
                for line in f:
                    if 'LOCAL_DRAM' in line:
                        m = re.search(r'([\d,]+)\s+MEM_LOAD', line)
                        if m:
                            local_dram = int(m.group(1).replace(',', ''))
                    if 'REMOTE_DRAM' in line:
                        m = re.search(r'([\d,]+)\s+MEM_LOAD', line)
                        if m:
                            remote_dram = int(m.group(1).replace(',', ''))

        rows.append({
            'run': run_label,
            'snapshot': tag,
            'numa_hit': numa_hit,
            'numa_miss': numa_miss,
            'cross_numa_rate_%': round(rate, 2) if rate is not None else None,
            'local_node_pages': local_node,
            'other_node_pages': other_node,
            'proc_local_mb': pid_metrics['local_mb'],
            'proc_remote_mb': pid_metrics['remote_mb'],
            'perf_local_dram': local_dram,
            'perf_remote_dram': remote_dram,
        })

    return pd.DataFrame(rows)


def plot_cross_numa_evolution(df, title, output_path):
    """Graphe d'évolution du taux cross-NUMA pendant le job."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Filtre pour n'avoir que les snapshots pendant le job (pas T_BEFORE)
    df_run = df[df['snapshot'] != 'T_BEFORE'].copy()
    df_run['snapshot_idx'] = range(len(df_run))

    # --- Graphe 1 : Taux cross-NUMA (%) ---
    ax1 = axes[0]
    if df_run['cross_numa_rate_%'].notna().any():
        ax1.bar(df_run['snapshot'], df_run['cross_numa_rate_%'],
                color=['#2ca02c' if r < 1 else '#d62728' for r in df_run['cross_numa_rate_%'].fillna(0)],
                edgecolor='black')
        ax1.set_title('Taux Cross-NUMA (numa_miss / total)', fontweight='bold')
        ax1.set_ylabel('Cross-NUMA Rate (%)')
        ax1.axhline(y=1, color='orange', linestyle='--', label='Seuil 1% (notable)')
        ax1.axhline(y=5, color='red', linestyle='--', label='Seuil 5% (sévère)')
        ax1.legend()
        ax1.grid(axis='y', alpha=0.5)
        for i, (_, row) in enumerate(df_run.iterrows()):
            if pd.notna(row['cross_numa_rate_%']):
                ax1.text(i, row['cross_numa_rate_%'] + 0.1,
                         f"{row['cross_numa_rate_%']:.1f}%",
                         ha='center', fontsize=9, fontweight='bold')

    # --- Graphe 2 : LOCAL vs REMOTE pages ---
    ax2 = axes[1]
    if df_run['other_node_pages'].sum() > 0 or df_run['local_node_pages'].sum() > 0:
        x = range(len(df_run))
        width = 0.35
        ax2.bar([i - width/2 for i in x], df_run['local_node_pages'],
                width, label='Local Node Pages', color='#2ca02c', edgecolor='black')
        ax2.bar([i + width/2 for i in x], df_run['other_node_pages'],
                width, label='Other Node Pages (cross-NUMA)', color='#d62728',
                edgecolor='black', hatch='//')
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(df_run['snapshot'].tolist())
        ax2.set_title('Pages Mémoire : Local vs Remote Node', fontweight='bold')
        ax2.set_ylabel('Nombre de pages')
        ax2.legend()
        ax2.grid(axis='y', alpha=0.5)

    fig.suptitle(title, fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"[OK] Graphe sauvegardé : {output_path}")
    plt.close()


def print_summary_table(df):
    """Affiche un tableau lisible avec les métriques clés."""
    print("\n" + "="*80)
    print(f"{'Snapshot':<15} {'numa_miss':>12} {'cross_NUMA%':>12} "
          f"{'other_pages':>12} {'REMOTE_DRAM':>12}")
    print("-"*80)
    for _, row in df.iterrows():
        remote_dram_str = str(row['perf_remote_dram']) \
                          if row['perf_remote_dram'] is not None else "N/A"
        rate_str = f"{row['cross_numa_rate_%']:.2f}%" \
                   if pd.notna(row['cross_numa_rate_%']) else "N/A"
        print(f"{row['snapshot']:<15} {row['numa_miss']:>12,} "
              f"{rate_str:>12} {row['other_node_pages']:>12,} "
              f"{remote_dram_str:>12}")
    print("="*80)

    # Interprétation
    df_job = df[df['snapshot'] != 'T_BEFORE']
    if not df_job.empty and df_job['cross_numa_rate_%'].notna().any():
        max_rate = df_job['cross_numa_rate_%'].max()
        print(f"\n📊 INTERPRÉTATION :")
        if max_rate < 0.5:
            print(f"  ✅ Cross-NUMA rate max = {max_rate:.2f}% → Quasi nul. Pas de cross-NUMA.")
            print(f"     La dégradation observée est due à la CONTENTION CPU (SMT/HyperThreading).")
        elif max_rate < 3:
            print(f"  ⚠️  Cross-NUMA rate max = {max_rate:.2f}% → Faible mais présent.")
            print(f"     Dégradation mixte : SMT + début de cross-NUMA.")
        else:
            print(f"  🔴 Cross-NUMA rate max = {max_rate:.2f}% → SIGNIFICATIF.")
            print(f"     La surcharge de pods force des accès mémoire cross-NUMA.")
            print(f"     C'est la PREUVE de l'objectif de l'Étape 1.")


def main():
    parser = argparse.ArgumentParser(description='Analyse des snapshots numastat')
    parser.add_argument('--dir', required=True,
                        help='Répertoire des snapshots (ex: results/numa_monitoring/overload-n16-seq/run1)')
    parser.add_argument('--all-runs', action='store_true',
                        help='Analyser tous les runs dans le répertoire parent')
    parser.add_argument('--output-dir', default='analysis',
                        help='Répertoire de sortie pour les graphes')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.all_runs:
        # Analyser chaque run et combiner
        run_dirs = sorted(glob.glob(os.path.join(args.dir, 'run*')))
        if not run_dirs:
            print(f"Aucun répertoire run* trouvé dans {args.dir}")
            return

        all_dfs = []
        for run_dir in run_dirs:
            run_label = os.path.basename(run_dir)
            df = analyze_run(run_dir, run_label)
            if not df.empty:
                all_dfs.append(df)
                print(f"\n--- {run_label} ---")
                print_summary_table(df)

        if all_dfs:
            df_all = pd.concat(all_dfs, ignore_index=True)
            job_name = os.path.basename(os.path.normpath(args.dir))
            out_plot = os.path.join(args.output_dir, f"numa_overload_{job_name}.png")
            # Utilise le dernier run pour le graphe
            plot_cross_numa_evolution(all_dfs[-1], f"NUMA Overload — {job_name}", out_plot)
    else:
        run_label = os.path.basename(os.path.normpath(args.dir))
        df = analyze_run(args.dir, run_label)
        if df.empty:
            print(f"Aucune donnée trouvée dans {args.dir}")
            return
        print_summary_table(df)
        job_name = os.path.basename(os.path.dirname(os.path.normpath(args.dir)))
        out_plot = os.path.join(args.output_dir, f"numa_overload_{job_name}_{run_label}.png")
        plot_cross_numa_evolution(df, f"NUMA Overload — {job_name} {run_label}", out_plot)

    print(f"\n[DONE] Analyse terminée.")


if __name__ == "__main__":
    main()
