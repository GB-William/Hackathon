# PhotoDesk — Hackathon Agence de Presse

Application web locale de gestion et taggage de photos UHD.

## Lancement rapide

```bash
pip install flask pillow
python app.py
```
Ouvrir http://localhost:5000

## Structure du projet

```
hackathon/
├── app.py            # Serveur Flask
├── indexer.py        # Génération miniatures & vignettes + cache
├── Images/           # Photos UHD originales (déposées ici)
│   ├── 2026_02_Londres/
│   │   ├── Chesters/
│   │   └── ...
│   └── 2026_01_Biaritz/
├── Miniatures/       # Max 800x600px (même arborescence)
├── Vignettes/        # Max 160x120px (même arborescence)
├── templates/
│   └── index.html
└── .cache.json       # Cache global des images indexées
```

## Fonctionnalités

### Affichage
- Galerie vignettes (160x120) en grille responsive
- Double-clic sur vignette → miniature (800x600)
- Clic "Voir l'originale UHD" → image originale

### Navigation
- Arborescence : Images/ → sous-répertoires → sous-sous-répertoires (max 2 niveaux)
- Filtre par tag dans la sidebar
- Filtre "sans tag" pour trouver les images non taggées

### Gestion par lots
- Sélection multiple via checkboxes
- "Tout sélectionner" / "Désélectionner"
- Tagger : ajouter / remplacer / retirer des tags sur la sélection
- Déplacer : move images (+ miniatures + vignettes + tags) vers un autre répertoire

### Tags
- Stockés dans `.tags.json` dans chaque répertoire
- Autocomplétion lors de la saisie
- Propagation automatique aux miniatures et vignettes

### Cache
- `.cache.json` à la racine
- Re-calcul uniquement si fichier modifié (hash + mtime)
- Ré-indexation manuelle via bouton "↻ Ré-indexer"
- Auto-indexation au démarrage

### Répertoires
- Création de nouveaux dossiers (sidebar inline ou modal)
- Hiérarchie : Images/ > sous-répertoire > sous-sous-répertoire

## Notes techniques
- Python + Flask + Pillow
- Pas de base de données SQL
- Stockage JSON pour les tags et le cache
- Ratio d'origine toujours respecté (Pillow thumbnail)
