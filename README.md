# M2614 - Service Python Uno Q SBC

Ce dépôt contient l'application Python qui s'exécute sur la partie Linux embarquée de l'Arduino Uno Q. Elle sert d'interface entre le firmware Arduino du robot et l'utilisateur pendant les opérations de calibration du capteur couleur.

Son rôle principal n'est pas de piloter le robot en temps réel. Les fonctions critiques restent sur le microcontrôleur. Ce service fournit plutôt :

- une interface web de capture couleur
- le stockage des échantillons dans un CSV
- l'analyse locale des centroïdes de classification
- des fonctions d'assistance comme le téléchargement du CSV et le redémarrage du MCU

## À quoi sert ce dépôt

Le service est utilisé conjointement avec :

- `M2614_LaFaceCacheeDeLaLune` pour la capture des mesures AS7341 côté MCU
- `ball-sorter` pour réinjecter les nouveaux centroïdes dans le classifieur embarqué

Le workflow nominal de recalibrage passe maintenant par cette application web. Le dépôt `ball-analyzer` reste utile comme référence ou outil hors ligne, mais n'est plus nécessaire pour l'utilisation courante.

## Prérequis

### Logiciels

- Python `3.13` ou plus récent
- `uv` pour installer et lancer l'application
- un système Linux embarqué fonctionnel sur l'Uno Q si vous déployez sur la carte cible

### Services et accès nécessaires

- le firmware Arduino principal doit être en mode calibration couleur
- le socket RouterBridge doit être disponible sur `unix:///var/run/arduino-router.sock`
- la commande `arduino-reset` doit être disponible si vous voulez utiliser le redémarrage du MCU depuis l'interface

## Installation locale

```powershell
uv sync
uv run main.py
```

Par défaut, l'application écoute sur `0.0.0.0:8000`.

Vous pouvez changer l'écoute avec les variables d'environnement suivantes :

- `M2614_HOST`
- `M2614_PORT`

## Déploiement sur l'Uno Q

Le dépôt contient un service systemd de référence : `M2614.service`.

Dans sa configuration actuelle :

- utilisateur : `arduino`
- répertoire de travail : `/home/arduino/app`
- commande de démarrage : `/home/arduino/.local/bin/uv run main.py`

Ce fichier est une bonne base pour un déploiement persistant sur la carte cible, mais les chemins doivent rester cohérents avec l'installation réelle du projet sur le SBC Linux.

## Interface web

L'application expose une page web principale à la racine `/`. Elle permet de :

- choisir une couleur de balle
- démarrer une session de capture
- arrêter une session en cours
- réinitialiser le CSV de calibration
- télécharger le CSV courant
- lancer l'analyse des centroïdes
- redémarrer le MCU

## Routes utiles

Les routes les plus importantes sont :

- `GET /` : interface web principale
- `GET /health` : état simplifié du service
- `GET /api/gather/status` : état détaillé de la session et de l'analyse
- `POST /api/gather/start` : démarre une capture étiquetée
- `POST /api/gather/stop` : arrête la capture en cours
- `POST /api/gather/csv/reset` : recrée le CSV de calibration
- `GET /api/gather/csv/download` : télécharge le CSV courant
- `POST /api/gather/analysis/run` : calcule les centroïdes localement
- `POST /api/gather/device/reset` : relance le MCU via `arduino-reset`

## Workflow de recalibrage

### 1. Préparation

Avant de lancer une capture, il faut vérifier :

- que le firmware principal Uno Q a bien détecté l'AS7341 au démarrage
- que le service Python est lancé
- que le pont RouterBridge est connecté

### 2. Capture

Le workflow utilisateur est le suivant :

1. choisir une couleur dans l'interface
2. démarrer la capture
3. présenter les balles correspondantes
4. laisser le service compter les échantillons
5. attendre l'arrêt automatique à `100` échantillons ou arrêter manuellement

Le service enregistre chaque ligne au format :

```text
color_name,channel1,channel2,channel3,channel4,channel5,channel6,channel7,channel8,channel9,channel10
```

### 3. Analyse

Une fois le CSV suffisamment rempli, l'utilisateur peut lancer l'analyse directement depuis l'interface. L'application :

- charge les données labellisées
- calcule les centroïdes de classes
- estime un seuil pour les inconnus
- produit plusieurs graphiques de contrôle
- génère le code C++ à recopier dans `ball-sorter/classification.cpp`

### 4. Réinjection dans le trieur

Le résultat final de cette application n'est pas un firmware. C'est un jeu de constantes et d'indicateurs qui doivent ensuite être reportés dans le dépôt `ball-sorter`, puis recompilés sur la Seeeduino Nano.

## Fichiers générés et persistants

Pendant l'utilisation, le service produit principalement :

- `data/color_sensor_samples.csv` : mesures capturées et étiquetées
- `data/analysis/last_centroid_analysis.json` : dernier résultat d'analyse conservé entre deux redémarrages
- `static/generated/analysis/` : graphiques de contrôle consultables depuis l'interface

Les graphiques générés comprennent notamment :

- la distribution des classes
- la projection PCA
- le profil des centroïdes
- la matrice de similarité cosinus

## Comportement du pont RouterBridge

L'application dialogue avec le MCU via RouterBridge. Dans ce projet, ce pont sert à des commandes simples et à une télémétrie de faible fréquence. Il ne doit pas être considéré comme un canal temps réel.

En pratique, l'application :

- appelle le MCU pour démarrer et arrêter les captures
- interroge l'état du capteur
- reçoit les notifications `color_sensor.sample`
- met à jour l'état de l'interface en conséquence

Si le pont n'est pas connecté, l'interface reste accessible mais la capture ne peut pas démarrer.

## Dépannage rapide

### L'interface web s'ouvre mais la capture ne démarre pas

- vérifier que RouterBridge est connecté
- vérifier que le capteur AS7341 a été détecté au boot du sketch Uno Q
- vérifier que le firmware principal est bien entré en mode calibration

### Le bouton d'analyse échoue

- vérifier que le CSV existe et contient des échantillons suffisants
- vérifier que plusieurs classes ont bien été capturées
- vérifier les permissions d'écriture dans `data/` et `static/generated/analysis/`

### Le redémarrage du MCU ne fonctionne pas

- vérifier la disponibilité de `arduino-reset`
- vérifier que le service tourne avec un utilisateur autorisé à exécuter cette commande

### Les fichiers semblent disparaître après redémarrage

- vérifier que le répertoire de travail du service systemd correspond bien à l'emplacement de l'application
- vérifier que `data/` et `static/generated/analysis/` sont persistants

## Fichiers importants

- `main.py` : point d'entrée Uvicorn
- `app/` : logique applicative FastAPI, état et analyse
- `bridge.py` : client RouterBridge local
- `M2614.service` : base de service systemd pour le SBC Linux
- `pyproject.toml` : dépendances et prérequis Python

## Documentation Doxygen

La documentation Doxygen de ce dépôt utilise ce README comme page principale et complète cette vue par la documentation du code Python utile à l'exploitation et à la maintenance du service.
