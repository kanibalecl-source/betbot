from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REMOVE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
REMOVE_SUFFIXES = {".pyc", ".pyo", ".audit_backup"}
for path in sorted(ROOT.rglob("*"), key=lambda p: len(p.parts), reverse=True):
    if path.is_dir() and path.name in REMOVE_DIRS:
        shutil.rmtree(path, ignore_errors=True)
    elif path.is_file() and (path.suffix in REMOVE_SUFFIXES or path.name in {".DS_Store"}):
        path.unlink(missing_ok=True)
print("Repo cleaned: cache/build artifacts removed.")
