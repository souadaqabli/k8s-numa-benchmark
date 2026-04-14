#!/bin/bash
POD_ID=${POD_ID:-"local"}
TARGET_THREAD=0 # Or 2 depends on NUMA test

echo "--- PHASE 1 : Collecting Data ---"
# Ce script va lancer mem_stress3, récupérer Perf, Latence, Min, Max, STD et sauver le CSV
taskset -c $TARGET_THREAD python3 script.py

echo "--- PHASE 2 : Generating plots ---"
# Ces scripts ne font QUE lire le CSV et générer les images (plus de calculs CPU)
python3 plot_micro_analysis_seq.py
python3 plot_micro_analysis_rand.py
python3 plot_micro_analysis_global.py

echo "FINISHED !"