"""
indexer.py - Script d'indexation des images
Génère miniatures (800x600 max) et vignettes (160x120 max)
Met à jour le cache global
"""
import os
import json
import hashlib
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "Images"
MINIATURES_DIR = BASE_DIR / "Miniatures"
VIGNETTES_DIR = BASE_DIR / "Vignettes"
CACHE_FILE = BASE_DIR / ".cache.json"

MINI_MAX = (800, 600)
VIGN_MAX = (160, 120)

SUPPORTED = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}


def get_relative_path(path: Path, base: Path) -> str:
    return str(path.relative_to(base))


def fix_exif_orientation(img: Image.Image) -> Image.Image:
    """Corrige l'orientation d'une image selon ses métadonnées EXIF."""
    try:
        exif = img.getexif()
        orientation = exif.get(274)  # 274 = tag Orientation
        rotations = {
            3: Image.ROTATE_180,
            6: Image.ROTATE_270,
            8: Image.ROTATE_90,
        }
        if orientation in rotations:
            img = img.transpose(rotations[orientation])
    except Exception:
        pass
    return img


def make_thumbnail(src: Path, dst: Path, max_size: tuple):
    """Crée une miniature en respectant le ratio d'origine et l'orientation EXIF."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        src_mtime = src.stat().st_mtime
        dst_mtime = dst.stat().st_mtime
        if dst_mtime >= src_mtime:
            return False  # Déjà à jour
    with Image.open(src) as img:
        img = fix_exif_orientation(img)
        img = img.convert("RGB")
        img.thumbnail(max_size, Image.LANCZOS)
        img.save(dst, quality=85, optimize=True)
    return True


def get_file_hash(path: Path) -> str:
    stat = path.stat()
    return hashlib.md5(f"{path}{stat.st_size}{stat.st_mtime}".encode()).hexdigest()


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"images": {}, "dirs": {}}


def save_cache(cache: dict):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def load_tags(directory: Path) -> dict:
    tags_file = directory / ".tags.json"
    if tags_file.exists():
        with open(tags_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_tags(directory: Path, tags: dict):
    tags_file = directory / ".tags.json"
    with open(tags_file, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)


def scan_directory(img_dir: Path, depth: int = 0) -> list:
    """Scan récursif limité à 2 niveaux (sous-répertoire + sous-sous-répertoire)."""
    if depth > 2:
        return []
    images = []
    if not img_dir.exists():
        return images
    for item in sorted(img_dir.iterdir()):
        if item.is_file() and item.suffix.lower() in SUPPORTED:
            images.append(item)
        elif item.is_dir() and depth < 2:
            images.extend(scan_directory(item, depth + 1))
    return images


def index_all(force: bool = False):
    """Indexe toutes les images et génère miniatures + vignettes."""
    cache = load_cache()
    updated = 0
    total = 0

    for img_path in scan_directory(IMAGES_DIR):
        rel = get_relative_path(img_path, IMAGES_DIR)
        mini_path = MINIATURES_DIR / rel
        vign_path = VIGNETTES_DIR / rel

        file_hash = get_file_hash(img_path)
        cached = cache["images"].get(rel, {})

        if force or cached.get("hash") != file_hash or not mini_path.exists() or not vign_path.exists():
            try:
                make_thumbnail(img_path, mini_path, MINI_MAX)
                make_thumbnail(img_path, vign_path, VIGN_MAX)

                with Image.open(img_path) as img:
                    w, h = img.size

                cache["images"][rel] = {
                    "hash": file_hash,
                    "width": w,
                    "height": h,
                    "mini": str(get_relative_path(mini_path, MINIATURES_DIR)),
                    "vign": str(get_relative_path(vign_path, VIGNETTES_DIR)),
                }
                updated += 1
                print(f"  ✓ Indexé: {rel}")
            except Exception as e:
                print(f"  ✗ Erreur {rel}: {e}")
        total += 1

    # Nettoyer les entrées orphelines
    existing = {get_relative_path(p, IMAGES_DIR) for p in scan_directory(IMAGES_DIR)}
    orphans = [k for k in list(cache["images"].keys()) if k not in existing]
    for o in orphans:
        del cache["images"][o]
        print(f"  ~ Supprimé du cache: {o}")

    save_cache(cache)
    print(f"\nIndexation terminée: {updated}/{total} images traitées.")
    return cache


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    print("=== Indexation des images ===")
    index_all(force=force)