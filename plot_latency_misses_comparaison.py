import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def plot_comparison():
    df = pd.read_csv("results/memory_benchmark_results_full.csv")
    output_dir = "results"

    # Configuration de la grille 2x2
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()

    modes = [
        ("sequential_read", "Seq Read", "#1f77b4"),
        ("random_read", "Rand Read", "#ff7f0e"),
        ("sequential_write", "Seq Write", "#d62728"),
        ("random_write", "Rand Write", "#2ca02c")
    ]

    for i, (mode, label, color) in enumerate(modes):
        ax1 = axes[i]
        sub_df = df[df['pattern'] == mode].sort_values('size_kb')
        
        x = sub_df['size_kb']
        latency = sub_df['lat_ns']
        misses = sub_df['LLC_misses']

        # --- AXE GAUCHE : LATENCE ---
        ax1.set_xscale('log')
        ax1.set_yscale('log')
        ax1.plot(x, latency, color=color, marker='o', linewidth=2.5, label=f'Latence {label}')
        ax1.set_ylabel('Latence par accès (ns)', color=color, fontweight='bold')
        ax1.tick_params(axis='y', labelcolor=color)
        ax1.grid(True, which="both", ls="-", alpha=0.2)

        # --- AXE DROIT : LLC MISSES ---
        ax2 = ax1.twinx()
        ax2.set_yscale('log')
        ax2.plot(x, misses, color='black', linestyle='--', marker='x', alpha=0.5, label='LLC Misses')
        ax2.set_ylabel('LLC Load Misses', color='black', alpha=0.7)
        ax2.tick_params(axis='y', labelcolor='black')

        # Annotations des seuils de cache
        ax1.axvline(x=256, color='grey', linestyle=':', alpha=0.4) # Limite L2
        ax1.axvline(x=4096, color='red', linestyle=':', alpha=0.4)  # Limite L3 (Bascule RAM)

        ax1.set_title(f"Impact des Misses : {label}", fontweight='bold')
        if i >= 2: ax1.set_xlabel('Taille du Bloc (Ko)', fontweight='bold')

    plt.suptitle("Analyse de Corrélation : Latence vs Explosion des LLC Misses", fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    save_path = os.path.join(output_dir, "latency_misses_comparison_4modes.png")
    plt.savefig(save_path)
    print(f"[OK] Graphique comparatif généré : {save_path}")
    plt.show()

if __name__ == "__main__":
    plot_comparison()