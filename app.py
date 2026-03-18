"""
app.py - Application Flask principale
Interface web pour naviguer, tagger et déplacer les photos
"""
import os
import json
import shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort, redirect, url_for

from indexer import (
    IMAGES_DIR, MINIATURES_DIR, VIGNETTES_DIR, CACHE_FILE,
    load_cache, save_cache, load_tags, save_tags,
    index_all, scan_directory, get_relative_path, SUPPORTED
)

app = Flask(__name__)
BASE_DIR = Path(__file__).parent


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_subdirs(base: Path = IMAGES_DIR, depth: int = 0) -> list:
    """Liste les sous-répertoires (max 2 niveaux)."""
    if not base.exists() or depth > 1:
        return []
    result = []
    for item in sorted(base.iterdir()):
        if item.is_dir():
            rel = get_relative_path(item, IMAGES_DIR)
            children = get_subdirs(item, depth + 1) if depth < 1 else []
            result.append({"name": item.name, "path": rel, "children": children})
    return result


def get_images_in_dir(rel_dir: str, cache: dict) -> list:
    """Retourne les images d'un répertoire (non récursif)."""
    target = IMAGES_DIR / rel_dir if rel_dir else IMAGES_DIR
    images = []
    if not target.exists():
        return images
    for item in sorted(target.iterdir()):
        if item.is_file() and item.suffix.lower() in SUPPORTED:
            rel = get_relative_path(item, IMAGES_DIR)
            info = cache["images"].get(rel, {})
            info["rel"] = rel
            info["name"] = item.name
            images.append(info)
    return images


def get_all_tags(cache: dict) -> set:
    """Collecte tous les tags existants."""
    all_tags = set()
    for img_dir in [IMAGES_DIR] + list(IMAGES_DIR.rglob("*")):
        if img_dir.is_dir():
            tags_data = load_tags(img_dir)
            for tags in tags_data.values():
                all_tags.update(tags)
    return sorted(all_tags)


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    cache = load_cache()
    dirs = get_subdirs()
    rel_dir = request.args.get("dir", "")
    tag_filter = request.args.get("tag", "")
    no_tag = request.args.get("no_tag", "")

    images = get_images_in_dir(rel_dir, cache)

    # Charger les tags du répertoire courant
    current_dir_path = IMAGES_DIR / rel_dir if rel_dir else IMAGES_DIR
    tags_data = load_tags(current_dir_path)

    # Enrichir les images avec leurs tags
    for img in images:
        img["tags"] = tags_data.get(img["name"], [])

    # Filtrer par tag
    if tag_filter:
        images = [img for img in images if tag_filter in img.get("tags", [])]
    elif no_tag:
        images = [img for img in images if not img.get("tags")]

    all_tags = get_all_tags(cache)
    total_images = len(cache.get("images", {}))

    return render_template("index.html",
        dirs=dirs,
        images=images,
        current_dir=rel_dir,
        tag_filter=tag_filter,
        no_tag=no_tag,
        all_tags=all_tags,
        total_images=total_images,
    )


@app.route("/vignette/<path:rel>")
def serve_vignette(rel):
    path = VIGNETTES_DIR / rel
    if not path.exists():
        abort(404)
    return send_file(path)


@app.route("/miniature/<path:rel>")
def serve_miniature(rel):
    path = MINIATURES_DIR / rel
    if not path.exists():
        abort(404)
    return send_file(path)


@app.route("/original/<path:rel>")
def serve_original(rel):
    path = IMAGES_DIR / rel
    if not path.exists():
        abort(404)
    return send_file(path)


@app.route("/api/index", methods=["POST"])
def api_index():
    force = request.json.get("force", False)
    cache = index_all(force=force)
    return jsonify({"success": True, "count": len(cache["images"])})


@app.route("/api/tags", methods=["POST"])
def api_set_tags():
    data = request.json
    filenames = data.get("files", [])  # liste de noms de fichiers
    tags = data.get("tags", [])
    rel_dir = data.get("dir", "")
    action = data.get("action", "set")  # set | add | remove

    current_dir_path = IMAGES_DIR / rel_dir if rel_dir else IMAGES_DIR
    tags_data = load_tags(current_dir_path)

    for fname in filenames:
        current = set(tags_data.get(fname, []))
        if action == "set":
            current = set(tags)
        elif action == "add":
            current.update(tags)
        elif action == "remove":
            current -= set(tags)
        tags_data[fname] = sorted(current)

    save_tags(current_dir_path, tags_data)

    # Propager aux miniatures et vignettes (même structure)
    for folder in [MINIATURES_DIR, VIGNETTES_DIR]:
        target_dir = folder / rel_dir if rel_dir else folder
        target_dir.mkdir(parents=True, exist_ok=True)
        save_tags(target_dir, tags_data)

    return jsonify({"success": True})


@app.route("/api/move", methods=["POST"])
def api_move():
    data = request.json
    filenames = data.get("files", [])
    src_dir = data.get("src_dir", "")
    dst_dir = data.get("dst_dir", "")

    if not dst_dir:
        return jsonify({"success": False, "error": "Destination manquante"})

    moved = []
    errors = []

    for fname in filenames:
        for base in [IMAGES_DIR, MINIATURES_DIR, VIGNETTES_DIR]:
            src_path = (base / src_dir / fname) if src_dir else (base / fname)
            dst_folder = (base / dst_dir) if dst_dir else base
            dst_folder.mkdir(parents=True, exist_ok=True)
            dst_path = dst_folder / fname

            if src_path.exists():
                try:
                    shutil.move(str(src_path), str(dst_path))
                except Exception as e:
                    errors.append(str(e))

        # Déplacer aussi les tags
        src_img_dir = IMAGES_DIR / src_dir if src_dir else IMAGES_DIR
        dst_img_dir = IMAGES_DIR / dst_dir if dst_dir else IMAGES_DIR
        src_tags = load_tags(src_img_dir)
        dst_tags = load_tags(dst_img_dir)

        if fname in src_tags:
            dst_tags[fname] = src_tags.pop(fname)
            save_tags(src_img_dir, src_tags)
            save_tags(dst_img_dir, dst_tags)
            for folder in [MINIATURES_DIR, VIGNETTES_DIR]:
                d = folder / dst_dir if dst_dir else folder
                save_tags(d, dst_tags)

        moved.append(fname)

    # Mettre à jour le cache
    index_all()

    return jsonify({"success": True, "moved": moved, "errors": errors})


@app.route("/api/mkdir", methods=["POST"])
def api_mkdir():
    data = request.json
    parent = data.get("parent", "")
    name = data.get("name", "").strip()

    if not name or "/" in name or ".." in name:
        return jsonify({"success": False, "error": "Nom invalide"})

    for base in [IMAGES_DIR, MINIATURES_DIR, VIGNETTES_DIR]:
        new_dir = (base / parent / name) if parent else (base / name)
        new_dir.mkdir(parents=True, exist_ok=True)

    return jsonify({"success": True})


@app.route("/api/all_tags")
def api_all_tags():
    cache = load_cache()
    return jsonify(sorted(get_all_tags(cache)))


@app.route("/api/search_by_tag")
def api_search_by_tag():
    tag = request.args.get("tag", "")
    rel_dir = request.args.get("dir", "")
    cache = load_cache()

    results = []
    search_base = IMAGES_DIR / rel_dir if rel_dir else IMAGES_DIR

    for dirpath in [search_base] + [d for d in search_base.rglob("*") if d.is_dir()]:
        tags_data = load_tags(dirpath)
        for fname, ftags in tags_data.items():
            if tag in ftags:
                fpath = dirpath / fname
                if fpath.exists():
                    rel = get_relative_path(fpath, IMAGES_DIR)
                    info = cache["images"].get(rel, {})
                    info["rel"] = rel
                    info["name"] = fname
                    info["tags"] = ftags
                    info["dir"] = get_relative_path(dirpath, IMAGES_DIR)
                    results.append(info)

    return jsonify(results)


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        # Astuce : connexion UDP factice pour trouver l'IP sortante réelle
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = socket.gethostbyname(hostname)

    print("=== Démarrage du serveur ===")
    print("Indexation initiale...")
    index_all()
    print(f"\n✓ Serveur lancé :")
    print(f"  → Local    : http://localhost:5000")
    print(f"  → Réseau   : http://{local_ip}:5000")
    print(f"  → Hostname : http://{hostname}:5000")
    print("\nCtrl+C pour arrêter\n")
    app.run(host="0.0.0.0", port=5000, debug=False)