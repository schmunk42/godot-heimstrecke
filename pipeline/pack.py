# file generated with AI assistance: Claude Code - 2026-10-22 22:43:00 UTC
"""Stage 3: pack a built world into one shareable .world file.

The package <out>/<id>-<version>.world is a ZIP (deflate) with all
entries at the root: world.json first, then horizon.glb, the tiles in
manifest order and their non-empty tree files (<tile>.trees,
<tile>.trunks) if the manifest lists trees, and roads.bin if it lists
roads; nothing else (no metrics, no extract, no raw data). Its
world.json is the build's manifest plus `built`, `commit`, `size_bytes`
(uncompressed bytes of all files except world.json) and `files` (their
SHA-256), validated against worlds/world.schema.json before anything is
written. The package is written as .part and renamed when complete.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator
from world import RecipeError, load_recipe, manifest_fields

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "worlds" / "world.schema.json"
MANIFEST = "world.json"
MAX_BYTES = 500_000_000
CHUNK = 1 << 20


class PackError(RuntimeError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=REPO, capture_output=True, text=True,
                             check=True)
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def read_manifest(world_dir):
    path = world_dir / MANIFEST
    if not path.is_file():
        raise PackError(f"world {world_dir} not found (no {MANIFEST}), "
                        "build it first")
    try:
        manifest = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise PackError(f"{path}: invalid JSON ({err})") from None
    if not isinstance(manifest, dict):
        raise PackError(f"{path}: manifest must be a JSON object")
    return manifest


def package_files(world_dir, manifest):
    """horizon.glb, the tiles in manifest order and the tree files, all
    must exist."""
    names = [manifest.get("horizon"), *manifest.get("tiles", [])]
    for key in ("roads", "road_names", "signs"):
        if manifest.get(key) is not None:
            names.append(manifest[key])
    for tile in (manifest.get("trees") or {}).get("tiles", []):
        if any(map(sum, tile.get("counts", []))):
            names.append(f"{tile.get('name')}.trees")
        if tile.get("trunks"):
            names.append(f"{tile.get('name')}.trunks")
    files = []
    for name in names:
        if not isinstance(name, str) or Path(name).name != name:
            raise PackError(f"{world_dir / MANIFEST}: bad file entry "
                            f"{name!r}")
        path = world_dir / name
        if not path.is_file():
            raise PackError(f"{path} listed in {MANIFEST} not found")
        files.append(path)
    return files


def packaged_manifest(recipe, manifest, files):
    """The packaged world.json in contract order."""
    head, tail = manifest_fields(recipe)
    build = {k: v for k, v in manifest.items()
             if k not in head and k not in tail}
    return {**head,
            "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "commit": git_commit(),
            **build, **tail,
            "size_bytes": sum(p.stat().st_size for p in files),
            "files": {p.name: sha256(p) for p in files}}


def validate(manifest):
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest),
                    key=lambda e: list(e.absolute_path))
    if errors:
        err = errors[0]
        raise PackError(f"manifest violates worlds/world.schema.json: "
                        f"{err.message} at {err.json_path}")


def write_package(path, manifest, files):
    part = path.with_name(path.name + ".part")
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST, json.dumps(manifest, indent=2,
                                             ensure_ascii=False))
            for p in files:
                zf.write(p, p.name)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return part


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", type=Path, required=True,
                    help="world recipe (worlds/<id>/world.json)")
    ap.add_argument("--world", type=Path, required=True,
                    help="built world directory (data/out/worlds/<id>)")
    ap.add_argument("--out", type=Path, required=True,
                    help="package directory (data/out/packages)")
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    args = ap.parse_args()

    recipe = load_recipe(args.recipe)
    manifest = read_manifest(args.world)
    if manifest.get("id") != recipe.id:
        raise PackError(f"{args.world / MANIFEST} is world "
                        f"{manifest.get('id')!r}, the recipe is "
                        f"{recipe.id!r}")
    files = package_files(args.world, manifest)
    packed = packaged_manifest(recipe, manifest, files)
    validate(packed)

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{recipe.id}-{recipe.version}.world"
    part = write_package(path, packed, files)
    size = part.stat().st_size
    if size > args.max_bytes:
        part.unlink()
        print(f"error: package {path} would be {size} bytes, more than "
              f"{args.max_bytes}", file=sys.stderr)
        sys.exit(3)
    part.replace(path)
    print(f"packed {path} bytes={size} files={len(files)} "
          f"uncompressed={packed['size_bytes']}")


if __name__ == "__main__":
    try:
        main()
    except (PackError, RecipeError) as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(2)
# - revised 2026-10-23 (roads.bin in the package)
# - revised 2026-10-23 (roads.bin, road_names.json, signs.json in the package)
