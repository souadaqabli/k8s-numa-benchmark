# Analyse des Résultats - Prefetching

## Résumé des Tests

### Test 1a : Sequential Read (1 GB)
- **Cycles** : 27694208563
- **Instructions** : 35531246438
- **Cache Misses** : 

### Test 1b : Random Read (1 GB)
- **Cycles** : 6413536497
- **Instructions** : 14412223807
- **Cache Misses** : 

## Comparaison

| Métrique | Sequential | Random | Ratio (Random/Seq) |
|----------|-----------|--------|-------------------|
| Cycles | 27694208563 | 6413536497 | ... |
| Cache Misses |  |  | ... |

## Interprétation

### Preuve du Prefetching :

1. **Cache Misses** :
   - Sequential devrait avoir BEAUCOUP MOINS de cache misses
   - Random devrait avoir BEAUCOUP de cache misses
   - Si Ratio > 10× → Le prefetcher est très efficace en sequential

2. **Cycles** :
   - Sequential devrait prendre moins de cycles
   - Random devrait être plus lent (plus de stalls)

3. **IPC (Instructions Per Cycle)** :
   - Sequential : IPC élevé (pipeline efficace)
   - Random : IPC faible (beaucoup de stalls)

### Résultats Attendus :

Si le prefetcher fonctionne bien :
- Cache miss rate Sequential : < 5%
- Cache miss rate Random : > 80%
- Ratio des cycles : Random prend 5-10× plus de cycles

## Fichiers de Résultats

- `seq_read.txt` : Compteurs hardware pour sequential read
- `rand_read.txt` : Compteurs hardware pour random read

## Prochaines Étapes

Pour une analyse plus détaillée :
1. Exécuter `python3 compare_methods.py` pour voir la différence de latence
2. Exécuter `python3 microarch_proof.py` pour les preuves complètes
3. Visualiser avec les graphiques générés
