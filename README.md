# M2614 La face cachée de la Lune

Repo du code Python tournant sur la Arduino Uno Q

## Dashboard web

Le projet contient maintenant un dashboard web placeholder lance par uvicorn via `uv run main.py`.

### Lancement local

```powershell
uv sync
uv run main.py
```

Par defaut, le serveur ecoute sur `0.0.0.0:8000`.
Vous pouvez changer le port avec la variable d'environnement `M2614_PORT`.

### Pages disponibles

- `/monitoring` : supervision du robot, du systeme de tri et zone reservee pour la carte LiDAR 2D
- `/control` : commandes placeholder pour les sequences de calibration, la selection du mode robot et le forcage du tri

### Etat actuel

- l'interface utilise Bootstrap 5.3 en assets locaux, sans dependance CDN
- les donnees robot, trieur et LiDAR sont encore des placeholders partages en memoire
- les boutons de calibration, le changement de mode et le forcage du tri appellent deja des endpoints backend prepares pour une future integration avec `bridge.py`
