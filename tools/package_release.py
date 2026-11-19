"""Add local user guide and runtime license texts to the portable release."""
import shutil
import argparse
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--release-dir", type=Path, default=root / "dist" / "CatMate")
release = parser.parse_args().release_dir
if not (release / "CatMate.exe").is_file():
    raise RuntimeError("Build CatMate.exe first")
for name in ("README.md", "THIRD_PARTY_NOTICES.md"):
    shutil.copy2(root / name, release / name)
shutil.copytree(root / "licenses", release / "licenses", dirs_exist_ok=True)
size = sum(p.stat().st_size for p in release.rglob("*") if p.is_file())
print(f"Portable release: {release} ({size / 1024 / 1024:.1f} MiB)")
