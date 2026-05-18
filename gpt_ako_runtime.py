from pathlib import Path
from gpt_match_value_engine import run_full_gpt_analysis

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    report = run_full_gpt_analysis(base_dir)
    print(f"OK: przeanalizowano {report.get('count', 0)} typów.")
    print("Wynik zapisany: data/gpt_analysis_report.json")
