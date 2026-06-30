#!/bin/bash

# Configuration de base (basée sur tes anciens fichiers)
IMAGE="memory-benchmark:v_numa4"
NODE_NAME="sdn2"
EXPERIMENT_MODE="work"

# Fonction pour générer le bloc YAML d'un Job
generate_job_yaml() {
  local JOB_NAME=$1
  local PARALLELISM=$2
  local PHYS_CPU_LIST=$3
  local MEM_NODE=$4
  local PATTERN=$5
  local FILE_PATH=$6

  cat <<EOF >> "$FILE_PATH"
---
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
spec:
  parallelism: ${PARALLELISM}
  completions: ${PARALLELISM}
  template:
    metadata:
      labels:
        app: ${JOB_NAME}
    spec:
      nodeName: ${NODE_NAME}
      containers:
      - name: benchmark
        image: ${IMAGE}
        command: ["/bin/bash", "-c"]
        args:
          - |
            export POD_ID=\$(hostname)
            export OUTPUT_DIR=/app/results/${JOB_NAME}_\${POD_ID}
            export BINDING_MODE="core"
            export PHYS_CPU_LIST="${PHYS_CPU_LIST}"
            export MEM_NODE="${MEM_NODE}"
            export PATTERN="${PATTERN}"
            export EXPERIMENT_MODE="${EXPERIMENT_MODE}"
            bash run_all.sh
        securityContext:
          privileged: true
        resources:
          requests:
            cpu: "1"
            memory: "1Gi"
          limits:
            cpu: "1"
            memory: "2Gi"
        volumeMounts:
        - name: results-volume
          mountPath: /app/results
        - name: script-python-volume
          mountPath: /app/scripts/script_controlled.py
          subPath: script_controlled.py
        - name: script-python-volume
          mountPath: /app/scripts/mem_stress_controlled.py
          subPath: mem_stress_controlled.py
        - name: script-python-volume
          mountPath: /app/run_all.sh
          subPath: run_all.sh
      restartPolicy: Never
      volumes:
      - name: results-volume
        hostPath:
          path: /home/sdnuser/k8s-numa-benchmark/results
          type: DirectoryOrCreate
      - name: script-python-volume
        configMap:
          name: script-benchmark-controlled
EOF
}

# Les deux patterns à tester
PATTERNS=("sequential" "random")

for PATTERN in "${PATTERNS[@]}"; do
  # Définir le dossier racine selon le pattern
  if [ "$PATTERN" == "sequential" ]; then
    BASE_DIR="deployments/scalability/seq"
    SUFFIX="seq"
  else
    BASE_DIR="deployments/scalability/rand"
    SUFFIX="rand"
  fi

  # Créer l'arborescence (Ajout de N6 et N10)
  mkdir -p ${BASE_DIR}/N4 ${BASE_DIR}/N6 ${BASE_DIR}/N8 ${BASE_DIR}/N10 ${BASE_DIR}/N12

  echo "Génération des fichiers YAML pour le pattern : $PATTERN ..."

  # ==========================================
  # PALIER N = 4 COEURS
  # ==========================================
  FILE_BASE="${BASE_DIR}/N4/baseline.yaml"
  > "$FILE_BASE"
  generate_job_yaml "bench-base-n4-numa0-${SUFFIX}" 2 "0,2" "0" "$PATTERN" "$FILE_BASE"
  generate_job_yaml "bench-base-n4-numa1-${SUFFIX}" 2 "1,3" "1" "$PATTERN" "$FILE_BASE"

  FILE_EXTR="${BASE_DIR}/N4/extreme.yaml"
  > "$FILE_EXTR"
  generate_job_yaml "bench-extr-n4-${SUFFIX}" 4 "0,2,4,6" "0" "$PATTERN" "$FILE_EXTR"

  FILE_CROSS="${BASE_DIR}/N4/cross-numa.yaml"
  > "$FILE_CROSS"
  generate_job_yaml "bench-cross-n4-numa0-${SUFFIX}" 2 "0,2" "1" "$PATTERN" "$FILE_CROSS"
  generate_job_yaml "bench-cross-n4-numa1-${SUFFIX}" 2 "1,3" "0" "$PATTERN" "$FILE_CROSS"

  FILE_EXCR="${BASE_DIR}/N4/extreme-cross.yaml"
  > "$FILE_EXCR"
  generate_job_yaml "bench-excr-n4-${SUFFIX}" 4 "0,2,4,6" "1" "$PATTERN" "$FILE_EXCR"

  # ==========================================
  # PALIER N = 6 COEURS (NOUVEAU)
  # ==========================================
  FILE_BASE="${BASE_DIR}/N6/baseline.yaml"
  > "$FILE_BASE"
  generate_job_yaml "bench-base-n6-numa0-${SUFFIX}" 3 "0,2,4" "0" "$PATTERN" "$FILE_BASE"
  generate_job_yaml "bench-base-n6-numa1-${SUFFIX}" 3 "1,3,5" "1" "$PATTERN" "$FILE_BASE"

  FILE_EXTR="${BASE_DIR}/N6/extreme.yaml"
  > "$FILE_EXTR"
  generate_job_yaml "bench-extr-n6-${SUFFIX}" 6 "0,2,4,6,8,10" "0" "$PATTERN" "$FILE_EXTR"

  FILE_CROSS="${BASE_DIR}/N6/cross-numa.yaml"
  > "$FILE_CROSS"
  generate_job_yaml "bench-cross-n6-numa0-${SUFFIX}" 3 "0,2,4" "1" "$PATTERN" "$FILE_CROSS"
  generate_job_yaml "bench-cross-n6-numa1-${SUFFIX}" 3 "1,3,5" "0" "$PATTERN" "$FILE_CROSS"

  FILE_EXCR="${BASE_DIR}/N6/extreme-cross.yaml"
  > "$FILE_EXCR"
  generate_job_yaml "bench-excr-n6-${SUFFIX}" 6 "0,2,4,6,8,10" "1" "$PATTERN" "$FILE_EXCR"

  # ==========================================
  # PALIER N = 8 COEURS
  # ==========================================
  FILE_BASE="${BASE_DIR}/N8/baseline.yaml"
  > "$FILE_BASE"
  generate_job_yaml "bench-base-n8-numa0-${SUFFIX}" 4 "0,2,4,6" "0" "$PATTERN" "$FILE_BASE"
  generate_job_yaml "bench-base-n8-numa1-${SUFFIX}" 4 "1,3,5,7" "1" "$PATTERN" "$FILE_BASE"

  FILE_EXTR="${BASE_DIR}/N8/extreme.yaml"
  > "$FILE_EXTR"
  generate_job_yaml "bench-extr-n8-${SUFFIX}" 8 "0,2,4,6,8,10,12,14" "0" "$PATTERN" "$FILE_EXTR"

  FILE_CROSS="${BASE_DIR}/N8/cross-numa.yaml"
  > "$FILE_CROSS"
  generate_job_yaml "bench-cross-n8-numa0-${SUFFIX}" 4 "0,2,4,6" "1" "$PATTERN" "$FILE_CROSS"
  generate_job_yaml "bench-cross-n8-numa1-${SUFFIX}" 4 "1,3,5,7" "0" "$PATTERN" "$FILE_CROSS"

  FILE_EXCR="${BASE_DIR}/N8/extreme-cross.yaml"
  > "$FILE_EXCR"
  generate_job_yaml "bench-excr-n8-${SUFFIX}" 8 "0,2,4,6,8,10,12,14" "1" "$PATTERN" "$FILE_EXCR"

  # ==========================================
  # PALIER N = 10 COEURS (NOUVEAU)
  # ==========================================
  FILE_BASE="${BASE_DIR}/N10/baseline.yaml"
  > "$FILE_BASE"
  generate_job_yaml "bench-base-n10-numa0-${SUFFIX}" 5 "0,2,4,6,8" "0" "$PATTERN" "$FILE_BASE"
  generate_job_yaml "bench-base-n10-numa1-${SUFFIX}" 5 "1,3,5,7,9" "1" "$PATTERN" "$FILE_BASE"

  FILE_EXTR="${BASE_DIR}/N10/extreme.yaml"
  > "$FILE_EXTR"
  generate_job_yaml "bench-extr-n10-${SUFFIX}" 10 "0,2,4,6,8,10,12,14,16,18" "0" "$PATTERN" "$FILE_EXTR"

  FILE_CROSS="${BASE_DIR}/N10/cross-numa.yaml"
  > "$FILE_CROSS"
  generate_job_yaml "bench-cross-n10-numa0-${SUFFIX}" 5 "0,2,4,6,8" "1" "$PATTERN" "$FILE_CROSS"
  generate_job_yaml "bench-cross-n10-numa1-${SUFFIX}" 5 "1,3,5,7,9" "0" "$PATTERN" "$FILE_CROSS"

  FILE_EXCR="${BASE_DIR}/N10/extreme-cross.yaml"
  > "$FILE_EXCR"
  generate_job_yaml "bench-excr-n10-${SUFFIX}" 10 "0,2,4,6,8,10,12,14,16,18" "1" "$PATTERN" "$FILE_EXCR"

  # ==========================================
  # PALIER N = 12 COEURS
  # ==========================================
  FILE_BASE="${BASE_DIR}/N12/baseline.yaml"
  > "$FILE_BASE"
  generate_job_yaml "bench-base-n12-numa0-${SUFFIX}" 6 "0,2,4,6,8,10" "0" "$PATTERN" "$FILE_BASE"
  generate_job_yaml "bench-base-n12-numa1-${SUFFIX}" 6 "1,3,5,7,9,11" "1" "$PATTERN" "$FILE_BASE"

  FILE_EXTR="${BASE_DIR}/N12/extreme.yaml"
  > "$FILE_EXTR"
  generate_job_yaml "bench-extr-n12-${SUFFIX}" 12 "0,2,4,6,8,10,12,14,16,18,20,22" "0" "$PATTERN" "$FILE_EXTR"

  FILE_CROSS="${BASE_DIR}/N12/cross-numa.yaml"
  > "$FILE_CROSS"
  generate_job_yaml "bench-cross-n12-numa0-${SUFFIX}" 6 "0,2,4,6,8,10" "1" "$PATTERN" "$FILE_CROSS"
  generate_job_yaml "bench-cross-n12-numa1-${SUFFIX}" 6 "1,3,5,7,9,11" "0" "$PATTERN" "$FILE_CROSS"

  FILE_EXCR="${BASE_DIR}/N12/extreme-cross.yaml"
  > "$FILE_EXCR"
  generate_job_yaml "bench-excr-n12-${SUFFIX}" 12 "0,2,4,6,8,10,12,14,16,18,20,22" "1" "$PATTERN" "$FILE_EXCR"

done

echo "Terminé ! L'arborescence et les 40 fichiers YAML ont été créés avec succès."