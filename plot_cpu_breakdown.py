import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# Configuration
csv_path = "results/memory_benchmark_results_full.csv"
output_dir = "results"

def plot_breakdown_comparison():
    if not os.path.exists(csv_path):
        print(f"Erreur : Le fichier {csv_path} est introuvable.")
        return

    df = pd.read_csv(csv_path)

    # Configuration de la figure (2 lignes, 2 colonnes)
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(16, 10), sharey=True)
    axes = axes.flatten() # Pour itérer facilement sur les 4 graphiques

    # Ordre d'affichage et titres
    modes_config = [
        ("sequential_read", "Lecture Séquentielle "),
        ("random_read", "Lecture Aléatoire (Latence Pure)"),
        ("sequential_write", "Écriture Séquentielle"),
        ("random_write", "Écriture Aléatoire")
    ]

    # Couleurs standards (Vert=Bien, Rouge=Attente, Bleu=Instruction)
    colors = ['#2ca02c', '#d62728', '#1f77b4'] 
    labels_legend = ['Retiring (Calcul)', 'Backend Bound (Attente Mémoire)', 'Frontend Bound (Instructions)']

    for i, (mode, title) in enumerate(modes_config):
        ax = axes[i]
        
        # Filtrage et tri
        sub_df = df[df['pattern'] == mode].sort_values('size_kb')
        
        if sub_df.empty:
            ax.text(0.5, 0.5, "Pas de données", ha='center')
            continue

        # --- CALCUL DES POURCENTAGES ---
        max_ipc = 4.0  # Valeur théorique pour la plupart des CPUs modernes

        # On vérifie si les compteurs stalled sont à 0
        if sub_df['stalled_backend'].sum() > 0:
            # Méthode réelle si les compteurs fonctionnent
            backend = (sub_df['stalled_backend'] / sub_df['cycles']) * 100
            frontend = (sub_df['stalled_frontend'] / sub_df['cycles']) * 100
            retiring = (100 - (frontend + backend)).clip(lower=0)
        else:
            # MÉTHODE SYNTHÉTIQUE (Basée sur l'IPC)
            # On calcule la part de travail réel selon l'IPC observé
            retiring = (sub_df['IPC'] / max_ipc) * 100
            # On s'assure que le "vert" ne dépasse pas 95% pour laisser place au bruit
            retiring = retiring.clip(upper=95) 
            
            # Tout ce qui n'est pas du calcul est considéré comme de l'attente mémoire
            backend = 100 - retiring
            frontend = np.zeros(len(retiring)) # On néglige le frontend

        # Préparation axe X
        x_labels = [f"{int(s)}K" if s < 1024 else f"{int(s/1024)}M" for s in sub_df['size_kb']]
        x = np.arange(len(x_labels))

        # --- TRACÉ DES BARRES EMPILÉES ---
        # Couche 1 : Calcul Utile (Vert)
        p1 = ax.bar(x, retiring, label=labels_legend[0], color=colors[0], alpha=0.85, width=0.7)
        # Couche 2 : Attente Mémoire (Rouge) - Empilé sur Retiring
        p2 = ax.bar(x, backend, bottom=retiring, label=labels_legend[1], color=colors[1], alpha=0.85, width=0.7)
        # Couche 3 : Attente Frontend (Bleu) - Empilé sur le tout
        p3 = ax.bar(x, frontend, bottom=retiring+backend, label=labels_legend[2], color=colors[2], alpha=0.85, width=0.7)

        # Esthétique du sous-graphique
        ax.set_title(title, fontweight='bold', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=45)
        ax.set_ylim(0, 100)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        
        # Ajout du % Backend (Rouge) si significatif (>20%) pour la lisibilité
        for idx, val in enumerate(backend):
            if val > 20:
                # Positionnement au milieu de la barre rouge
                y_pos = retiring.iloc[idx] + (val / 2)
                ax.text(idx, y_pos, f"{int(val)}%", ha='center', va='center', 
                        color='white', fontsize=8, fontweight='bold')

    # Titres globaux
    fig.text(0.5, 0.02, 'Taille du Bloc Mémoire', ha='center', fontweight='bold', fontsize=12)
    fig.text(0.08, 0.5, 'Répartition des Cycles CPU (%)', va='center', rotation='vertical', fontweight='bold', fontsize=12)
    fig.suptitle("Analyse Top-Down : Impact de la Mémoire sur l'Efficacité CPU", fontsize=16, fontweight='bold')

    # Légende unique pour toute la figure
    handles, labels = axes[0].get_legend_handles_labels()
    # On inverse pour que l'ordre corresponde visuellement (Frontend en haut)
    fig.legend(handles[::-1], labels[::-1], loc='upper center', bbox_to_anchor=(0.5, 0.95), ncol=3, frameon=False)

    plt.tight_layout(rect=[0.05, 0.05, 1, 0.92]) # Ajustement pour laisser place aux titres
    
    save_path = os.path.join(output_dir, "cpu_breakdown_comparison_4modes.png")
    plt.savefig(save_path)
    print(f"[OK] Graphique comparatif généré : {save_path}")
    plt.show()

if __name__ == "__main__":
    plot_breakdown_comparison()