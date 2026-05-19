from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
py_files = list(ROOT.rglob('*.py'))
cache = list(ROOT.rglob('__pycache__'))
readmes = list(ROOT.glob('README*'))
print({
    'python_files': len(py_files),
    'cache_dirs': len(cache),
    'top_level_readmes': len(readmes),
    'has_env_file': (ROOT / '.env').exists(),
    'has_fastapi_app': (ROOT / 'app' / 'main.py').exists(),
    'has_tests': (ROOT / 'tests').exists(),
})
