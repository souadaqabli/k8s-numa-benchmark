# Résumé de la Réorganisation du Projet

Date : 2026-06-30

---

## 1. Racine — fichiers déplacés

| Avant | Après |
|-------|-------|
| `generate_yaml.sh` | `scripts/generate_yaml.sh` |
| `measure_tax.sh` | `scripts/measure_tax.sh` |
| `monitoring_setup/` | `monitoring/` |

---

## 2. deployments/ — consolidation de 5 dossiers en 1

### Scénarios contrôlés (numactl-pinné, 4 pods)

| Avant | Après |
|-------|-------|
| `deployments/deployments_rand_controlled/deployment-contention-extreme-rand-time.yaml` | `deployments/controlled/rand/deployment-contention-extreme-rand-time.yaml` |
| `deployments/deployments_rand_controlled/deployment-contention-extreme-rand-work.yaml` | `deployments/controlled/rand/deployment-contention-extreme-rand-work.yaml` |
| `deployments/deployments_rand_controlled/deployment-contention-extreme-node1-rand-time.yaml` | `deployments/controlled/rand/deployment-contention-extreme-node1-rand-time.yaml` |
| `deployments/deployments_rand_controlled/deployment-contention-extreme-node1-rand-work.yaml` | `deployments/controlled/rand/deployment-contention-extreme-node1-rand-work.yaml` |
| `deployments/deployments_rand_controlled/deployment-cross-numa-rand-time.yaml` | `deployments/controlled/rand/deployment-cross-numa-rand-time.yaml` |
| `deployments/deployments_rand_controlled/deployment-cross-numa-rand-work.yaml` | `deployments/controlled/rand/deployment-cross-numa-rand-work.yaml` |
| `deployments/deployments_rand_controlled/deployment-native-rand-time.yaml` | `deployments/controlled/rand/deployment-native-rand-time.yaml` |
| `deployments/deployments_rand_controlled/deployment-native-rand-work.yaml` | `deployments/controlled/rand/deployment-native-rand-work.yaml` |
| `deployments/deployments_rand_controlled/deployment-topomanager-rand-time.yaml` | `deployments/controlled/rand/deployment-topomanager-rand-time.yaml` |
| `deployments/deployments_rand_controlled/deployment-topomanager-rand-work.yaml` | `deployments/controlled/rand/deployment-topomanager-rand-work.yaml` |
| `deployments/deployments_rand_controlled/pods-optimal-4-rand-time.yaml` | `deployments/controlled/rand/pods-optimal-4-rand-time.yaml` |
| `deployments/deployments_rand_controlled/pods-optimal-4-rand-work.yaml` | `deployments/controlled/rand/pods-optimal-4-rand-work.yaml` |
| `deployments/deployments_seq_controlled/deployment-contention-extreme-seq-time.yaml` | `deployments/controlled/seq/deployment-contention-extreme-seq-time.yaml` |
| `deployments/deployments_seq_controlled/deployment-contention-extreme-seq-work.yaml` | `deployments/controlled/seq/deployment-contention-extreme-seq-work.yaml` |
| `deployments/deployments_seq_controlled/deployment-contention-extreme-node1-seq-time.yaml` | `deployments/controlled/seq/deployment-contention-extreme-node1-seq-time.yaml` |
| `deployments/deployments_seq_controlled/deployment-contention-extreme-node1-seq-work.yaml` | `deployments/controlled/seq/deployment-contention-extreme-node1-seq-work.yaml` |
| `deployments/deployments_seq_controlled/deployment-cross-numa-seq-time.yaml` | `deployments/controlled/seq/deployment-cross-numa-seq-time.yaml` |
| `deployments/deployments_seq_controlled/deployment-cross-numa-seq-work.yaml` | `deployments/controlled/seq/deployment-cross-numa-seq-work.yaml` |
| `deployments/deployments_seq_controlled/deployment-native-seq-time.yaml` | `deployments/controlled/seq/deployment-native-seq-time.yaml` |
| `deployments/deployments_seq_controlled/deployment-native-seq-work.yaml` | `deployments/controlled/seq/deployment-native-seq-work.yaml` |
| `deployments/deployments_seq_controlled/deployment-topomanager-seq-time.yaml` | `deployments/controlled/seq/deployment-topomanager-seq-time.yaml` |
| `deployments/deployments_seq_controlled/deployment-topomanager-seq-work.yaml` | `deployments/controlled/seq/deployment-topomanager-seq-work.yaml` |
| `deployments/deployments_seq_controlled/pods-optimal-4-seq-time.yaml` | `deployments/controlled/seq/pods-optimal-4-seq-time.yaml` |
| `deployments/deployments_seq_controlled/pods-optimal-4-seq-work.yaml` | `deployments/controlled/seq/pods-optimal-4-seq-work.yaml` |

### Scalabilité (N4 à N20, tous scénarios)

| Avant | Après |
|-------|-------|
| `deployments_scalability_seq/N4/` à `N20/` + `hetero/` | `deployments/scalability/seq/N4/` à `N20/` + `hetero/` |
| `deployments_scalability_rand/N4/` à `N20/` + `hetero/` | `deployments/scalability/rand/N4/` à `N20/` + `hetero/` |

### Overload et Redis

| Avant | Après |
|-------|-------|
| `deployments_overload/N16/seq.yaml` | `deployments/overload/N16/seq.yaml` |
| `deployments_overload/N16/rand.yaml` | `deployments/overload/N16/rand.yaml` |
| `deployments_overload/N24/seq.yaml` | `deployments/overload/N24/seq.yaml` |
| `deployments_overload/N24/rand.yaml` | `deployments/overload/N24/rand.yaml` |
| `deployments_redis/redis-numa-pod.yaml` | `deployments/redis/redis-numa-pod.yaml` |

### Anciens YAML déplacés en legacy (versions préliminaires)

| Avant | Après |
|-------|-------|
| `deployments/deployment.yaml` | `deployments/legacy/deployment.yaml` |
| `deployments/deployment-k8s.yaml` | `deployments/legacy/deployment-k8s.yaml` |
| `deployments/deployment-baseline.yaml` | `deployments/legacy/deployment-baseline.yaml` |
| `deployments/deployment-numa.yaml` | `deployments/legacy/deployment-numa.yaml` |
| `deployments/deployment-contention-numa.yaml` | `deployments/legacy/deployment-contention-numa.yaml` |
| `deployments/deployment-contention-extreme.yaml` | `deployments/legacy/deployment-contention-extreme.yaml` |
| `deployments/deployment-contention-extreme-node1.yaml` | `deployments/legacy/deployment-contention-extreme-node1.yaml` |
| `deployments/deployment-contention-extreme-rand.yaml` | `deployments/legacy/deployment-contention-extreme-rand.yaml` |
| `deployments/deployment-contention-extreme-seq.yaml` | `deployments/legacy/deployment-contention-extreme-seq.yaml` |
| `deployments/deployment-contention-extreme-node1-rand.yaml` | `deployments/legacy/deployment-contention-extreme-node1-rand.yaml` |
| `deployments/deployment-contention-extreme-node1-seq.yaml` | `deployments/legacy/deployment-contention-extreme-node1-seq.yaml` |
| `deployments/deployment-contention-extreme-correct.yaml` | `deployments/legacy/deployment-contention-extreme-correct.yaml` |
| `deployments/deployment-contention-extreme-node1-correct.yaml` | `deployments/legacy/deployment-contention-extreme-node1-correct.yaml` |
| `deployments/deployment-cross-numa.yaml` | `deployments/legacy/deployment-cross-numa.yaml` |
| `deployments/deployment-cross-numa-rand.yaml` | `deployments/legacy/deployment-cross-numa-rand.yaml` |
| `deployments/deployment-cross-numa-seq.yaml` | `deployments/legacy/deployment-cross-numa-seq.yaml` |
| `deployments/deployment-cross-numa-correct.yaml` | `deployments/legacy/deployment-cross-numa-correct.yaml` |
| `deployments/pods-optimal-4-rand.yaml` | `deployments/legacy/pods-optimal-4-rand.yaml` |
| `deployments/pods-optimal-4-seq.yaml` | `deployments/legacy/pods-optimal-4-seq.yaml` |
| `deployments/pods-optimal-4-correct.yaml` | `deployments/legacy/pods-optimal-4-correct.yaml` |

### Scripts mis à jour suite au déplacement des deployments

| Fichier | Ligne | Avant | Après |
|---------|-------|-------|-------|
| `scripts/generate_yaml.sh` | 85 | `deployments_scalability_seq` | `deployments/scalability/seq` |
| `scripts/generate_yaml.sh` | 88 | `deployments_scalability_rand` | `deployments/scalability/rand` |
| `scripts/host/run_scalability_campaign.sh` | 44 | `deployments_scalability_${PATTERN}` | `deployments/scalability/${PATTERN}` |
| `scripts/host/run_scalability_campaign_2.sh` | 40 | `deployments_scalability_${PATTERN}` | `deployments/scalability/${PATTERN}` |
| `scripts/host/run_overload_campaign.sh` | 158 | `${REMOTE_PATH}/deployments_overload/` | `${REMOTE_PATH}/deployments/overload/` |

---

## 3. analysis/ — séparation scripts / outputs

### Scripts Python déplacés

| Avant | Après |
|-------|-------|
| `analysis/analysis_approach1/parser_perf.py` | `analysis/correlation/v1/parser_perf.py` |
| `analysis/analysis_approach1/parser_rapl.py` | `analysis/correlation/v1/parser_rapl.py` |
| `analysis/analysis_approach1/correlation_perf_rapl.py` | `analysis/correlation/v1/correlation_perf_rapl.py` |
| `analysis/analysis_v2/parser_perf_v2.py` | `analysis/correlation/v2/parser_perf_v2.py` |
| `analysis/analysis_v2/parser_rapl_v2.py` | `analysis/correlation/v2/parser_rapl_v2.py` |
| `analysis/analysis_v2/correlation_perf_rapl_v2.py` | `analysis/correlation/v2/correlation_perf_rapl_v2.py` |
| `analysis/generate_plots_rapl.py` | `analysis/energy/generate_plots_rapl.py` |
| `analysis/generate_plots_rapl_2.py` | `analysis/energy/generate_plots_rapl_2.py` |
| `analysis/generate_plots_rapl_instructions.py` | `analysis/energy/generate_plots_rapl_instructions.py` |
| `analysis/generate_plots_rapl_instructions_native.py` | `analysis/energy/generate_plots_rapl_instructions_native.py` |
| `analysis/generate_plots_rapl_instructions_scale.py` | `analysis/energy/generate_plots_rapl_instructions_scale.py` |
| `analysis/generate_plots_rapl_power.py` | `analysis/energy/generate_plots_rapl_power.py` |
| `analysis/generate_plots_rapl_power_native.py` | `analysis/energy/generate_plots_rapl_power_native.py` |
| `analysis/energy_vs_cores.py` | `analysis/energy/energy_vs_cores.py` |
| `analysis/energy_vs_cores_2.py` | `analysis/energy/energy_vs_cores_2.py` |
| `analysis/energy_vs_cores_normalized.py` | `analysis/energy/energy_vs_cores_normalized.py` |
| `analysis/generate_perf_plots.py` | `analysis/performance/generate_perf_plots.py` |
| `analysis/plots_sizes_timebound.py` | `analysis/performance/plots_sizes_timebound.py` |
| `analysis/plots_sizes_workbound.py` | `analysis/performance/plots_sizes_workbound.py` |
| `analysis/analyze_correlation_overload.py` | `analysis/numa/analyze_correlation_overload.py` |
| `analysis/analyze_native_variance.py` | `analysis/numa/analyze_native_variance.py` |
| `analysis/parse_numastat.py` | `analysis/numa/parse_numastat.py` |
| `analysis/plot_numa_visualization_native_asym.py` | `analysis/numa/plot_numa_visualization_native_asym.py` |
| `analysis/generate_tables.py` | `analysis/tables/generate_tables.py` |
| `analysis/extract_instructions.py` | `analysis/tables/extract_instructions.py` |
| `analysis/extract_instructions_scalability.py` | `analysis/tables/extract_instructions_scalability.py` |

### Outputs générés (PNG, CSV) — toujours sur disque, jamais sur GitHub

Les fichiers suivants restent dans `analysis/` sur le disque local mais sont exclus
de git par `.gitignore` (`*.png`, `*.csv`). Ils ne seront jamais poussés sur GitHub.

```
analysis/*.png                          (scalability_rand.png, work_bound_plot.png, etc.)
analysis/*.csv                          (normalized_table_rand.csv, normalized_table_seq.csv)
analysis/time_bound/*.png
analysis/work_bound/*.png
analysis/correlation/v1/*.png + *.csv   (anciennement analysis_approach1/)
analysis/correlation/v2/*.png + *.csv   (anciennement analysis_v2/)
```

---

## 4. Fichiers non touchés (restent à leur place)

```
run_all.sh
Dockerfile
.dockerignore
deployments/tax_job.yaml
scripts/script_controlled.py
scripts/script.py
scripts/mem_stress3.py
scripts/mem_stress_controlled.py
scripts/run_micro_analysis.py
scripts/run_micro_analysis_rand.py
scripts/run_micro_analysis_seq.py
scripts/analyze_pcm.py
scripts/host/run_overload_campaign.sh       (chemin mis à jour, logique intacte)
scripts/host/run_scalability_campaign.sh    (chemin mis à jour, logique intacte)
scripts/host/run_scalability_campaign_2.sh  (chemin mis à jour, logique intacte)
scripts/redis/calculate_redis_metrics.py
scripts/redis/run_redis_benchmark.sh
monitoring/scaphandre-config.yaml
monitoring/scaphandre-monitor.yaml
monitoring/scaphandre-force-monitor.yaml
monitoring/scaphandre-prison-break.yaml
monitoring/scaphandre-rbac.yaml
monitoring/scaphandre-service.yaml
```

---

## 5. Fichiers ignorés par .gitignore (présents sur disque, absents de GitHub)

```
PLAN_TRAVAIL.md             document de travail interne
Dockerfile.test             dockerfile de test temporaire
analysis_k8s_backup/        dossier de backup
results_k8s_backup/         dossier de backup
__pycache__/                bytecode Python
*.png  *.csv  *.tar         outputs générés et archives
results/                    données brutes
data/                       données sources
figures/                    figures générées
plots/                      anciens scripts et plots
archive/                    archives tar
```

---

## 6. ALERTES — À résoudre avant le commit

### Alerte 1 — monitoring/scaphandre/ contient le code source complet de Scaphandre

Le dossier `monitoring/scaphandre/` est le dépôt Rust complet de Scaphandre
(Cargo.toml, src/, helm/, CI GitHub Actions, docs...) — des centaines de fichiers.
Tu ne veux pas pousser ça dans ton repo.

**Options :**
- Supprimer `monitoring/scaphandre/` et ne garder que les 6 YAML de config qui sont
  directement dans `monitoring/`
- Ou ajouter `monitoring/scaphandre/` au `.gitignore`

### Alerte 2 — plots/ contient des scripts Python ignorés par .gitignore

Les fichiers suivants sont du code source mais sont ignorés car `plots/` est dans `.gitignore` :

```
plots/perf_plots_all_tests.py
plots/plots_comparison.py
plots/rapl_perf_plots.py
plots/rapl_plot_all_tests.py
```

**Options :**
- Les déplacer dans `analysis/performance/` pour qu'ils soient trackés
- Ou les laisser ignorés si ce sont des scripts obsolètes
