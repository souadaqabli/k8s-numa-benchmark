#!/bin/bash

# 1. Lecture de l'énergie initiale (micro-Joules)
start_pkg0=$(cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj)
start_pkg1=$(cat /sys/class/powercap/intel-rapl/intel-rapl:1/energy_uj)
start_dram0=$(cat /sys/class/powercap/intel-rapl/intel-rapl:0/intel-rapl:0:0/energy_uj)
start_dram1=$(cat /sys/class/powercap/intel-rapl/intel-rapl:1/intel-rapl:1:0/energy_uj)

echo "Exécution en cours : $@"
# 2. Lancement de la commande et chronométrage
/usr/bin/time -f "Temps écoulé : %e secondes" "$@"

# 3. Lecture de l'énergie finale
end_pkg0=$(cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj)
end_pkg1=$(cat /sys/class/powercap/intel-rapl/intel-rapl:1/energy_uj)
end_dram0=$(cat /sys/class/powercap/intel-rapl/intel-rapl:0/intel-rapl:0:0/energy_uj)
end_dram1=$(cat /sys/class/powercap/intel-rapl/intel-rapl:1/intel-rapl:1:0/energy_uj)

# 4. Calcul de la différence et conversion en Joules
j_pkg0=$(echo "scale=2; ($end_pkg0 - $start_pkg0) / 1000000" | bc)
j_pkg1=$(echo "scale=2; ($end_pkg1 - $start_pkg1) / 1000000" | bc)
j_dram0=$(echo "scale=2; ($end_dram0 - $start_dram0) / 1000000" | bc)
j_dram1=$(echo "scale=2; ($end_dram1 - $start_dram1) / 1000000" | bc)
total=$(echo "$j_pkg0 + $j_pkg1 + $j_dram0 + $j_dram1" | bc)

echo ""
echo "=== RÉSULTATS RAPL (Joules) ==="
echo "PKG 0  : $j_pkg0"
echo "PKG 1  : $j_pkg1"
echo "DRAM 0 : $j_dram0"
echo "DRAM 1 : $j_dram1"
echo "TOTAL  : $total"
echo "==============================="
