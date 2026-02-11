import matplotlib.pyplot as plt
import mem_stress2
import numpy as np
import os

def run_timeline_analysis(size_kb=16, iters=20000):
    size_bytes = size_kb * 1024

    output_dir = "results/analysis_seq_ticks"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Lancement de l'analyse temporelle pour {size_kb} Ko...")
    
    mem_stress2.sequential_read(size_bytes, 5000)
    # On récupère les résultats (le dernier élément est notre liste all_lats)
    res_read = mem_stress2.sequential_read(size_bytes, iters)

    mem_stress2.sequential_write(size_bytes, 5000)
    res_write = mem_stress2.sequential_write(size_bytes, iters)
    
    lats_read = np.array(res_read[-1]) / (size_bytes // 8)  # Latence par élément (ns)
    lats_write = np.array(res_write[-1]) / (size_bytes // 8) # Latence par élément (ns)

    plt.figure(figsize=(15, 7))
    
    # Trace Read
    plt.plot(lats_read, label='Sequential Read', color='#1f77b4', alpha=0.6, linewidth=0.5)
    # Trace Write
    plt.plot(lats_write, label='Sequential Write', color='#d62728', alpha=0.6, linewidth=0.5)

    # Lignes de référence (Moyenne)
    plt.axhline(y=np.mean(lats_read), color='blue', linestyle='--', label='Moyenne Read')
    plt.axhline(y=np.mean(lats_write), color='red', linestyle='--', label='Moyenne Write')

    plt.title(f"Analyse Itération par Itération ({size_kb} Ko, {iters} itérations)")
    plt.xlabel("Numéro de l'itération")
    plt.ylabel("Latence par élément (ns)")
    plt.yscale('log') # Très important pour voir les petits bruits et les gros pics
    plt.legend()

    save_path = os.path.join(output_dir, "analyse_seq_ticks_16ko-warmup.png")
    plt.savefig(save_path)
    plt.grid(True, which="both", ls="-", alpha=0.2)
    
    plt.show()

if __name__ == "__main__":
    run_timeline_analysis(size_kb=16) #changer la taille ici