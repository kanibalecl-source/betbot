"""
Advanced Learning Engine

Bezpieczna dodatkowa warstwa nauki statystycznej dla bota.
Moduł nie zmienia obecnej logiki typowania, nie uruchamia treningu po imporcie
oraz działa wyłącznie na danych historycznych zapisanych w CSV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_FILE = DATA_DIR / "results_history.csv"
HISTORY_FILE = DATA_DIR / "history.csv"
PICKS_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"
LEARNING_SNAPSHOT_FILE = DATA_DIR / "learning_snapshot.csv"


class AdvancedLearningEngine:
    """Liczy procenty, ROI, skuteczność i podpowiedzi bez ingerencji w core bota."""

    def _read_csv(self, path: Path) -> pd.DataFrame:
        try:
            if path.exists():
                return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
        return pd.DataFrame()

    def load_results(self) -> pd.DataFrame:
        frames = []
        for path in [RESULTS_FILE, HISTORY_FILE]:
            df = self._read_csv(path)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True, sort=False)
        return self._normalize_results(df)

    def load_current_picks(self) -> pd.DataFrame:
        return self._read_csv(PICKS_FILE)

    def load_live(self) -> pd.DataFrame:
        return self._read_csv(LIVE_FILE)

    def _normalize_results(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "won" not in df.columns and "result" in df.columns:
            df["won"] = df["result"].astype(str).str.lower().isin(["1", "true", "win", "won", "w", "green"])

        if "won" in df.columns:
            if df["won"].dtype != bool:
                df["won"] = df["won"].astype(str).str.lower().isin(["1", "true", "win", "won", "w", "green"])

        for column in ["profit", "confidence", "ev", "odds", "stake", "live_edge", "tempo_score", "pressure_index", "momentum_score_adv", "xg_pace"]:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        return df

    def performance_summary(self) -> Dict[str, float]:
        df = self.load_results()
        if df.empty:
            return {
                "bets": 0,
                "winrate_pct": 0.0,
                "roi_pct": 0.0,
                "profit": 0.0,
                "avg_confidence": 0.0,
            }

        bets = len(df)
        profit = float(df["profit"].sum()) if "profit" in df.columns else 0.0
        stake_sum = float(df["stake"].sum()) if "stake" in df.columns else float(bets)
        if stake_sum == 0:
            stake_sum = float(bets) if bets else 1.0

        winrate = float(df["won"].mean() * 100) if "won" in df.columns and bets else 0.0
        avg_confidence = float(df["confidence"].mean()) if "confidence" in df.columns else 0.0

        return {
            "bets": bets,
            "winrate_pct": round(winrate, 2),
            "roi_pct": round((profit / stake_sum) * 100, 2),
            "profit": round(profit, 2),
            "avg_confidence": round(avg_confidence, 2),
        }

    def group_performance(self, column: str) -> pd.DataFrame:
        df = self.load_results()
        if df.empty or column not in df.columns:
            return pd.DataFrame()

        aggregations = {"bets": (column, "count")}
        if "profit" in df.columns:
            aggregations["profit"] = ("profit", "sum")
            aggregations["avg_profit"] = ("profit", "mean")
        if "won" in df.columns:
            aggregations["winrate_pct"] = ("won", lambda x: round(float(x.mean() * 100), 2))
        if "stake" in df.columns and "profit" in df.columns:
            grouped = df.groupby(column).agg(**aggregations).reset_index()
            stake = df.groupby(column)["stake"].sum().reset_index(name="stake_sum")
            grouped = grouped.merge(stake, on=column, how="left")
            grouped["roi_pct"] = grouped.apply(
                lambda row: round((row.get("profit", 0) / row.get("stake_sum", 1)) * 100, 2) if row.get("stake_sum", 0) else 0,
                axis=1,
            )
            grouped = grouped.drop(columns=["stake_sum"], errors="ignore")
        else:
            grouped = df.groupby(column).agg(**aggregations).reset_index()
            if "profit" in grouped.columns:
                grouped["roi_pct"] = grouped["profit"].round(2)

        sort_col = "roi_pct" if "roi_pct" in grouped.columns else "bets"
        return grouped.sort_values(sort_col, ascending=False)

    def confidence_accuracy(self) -> pd.DataFrame:
        df = self.load_results()
        if df.empty or "confidence" not in df.columns:
            return pd.DataFrame()

        df = df.dropna(subset=["confidence"]).copy()
        if df.empty:
            return pd.DataFrame()

        df["confidence_bucket"] = pd.cut(
            df["confidence"],
            bins=[0, 50, 60, 70, 80, 90, 100],
            labels=["0-50", "50-60", "60-70", "70-80", "80-90", "90-100"],
            include_lowest=True,
        )

        aggregations = {"bets": ("confidence", "count"), "avg_confidence": ("confidence", "mean")}
        if "won" in df.columns:
            aggregations["real_winrate_pct"] = ("won", lambda x: round(float(x.mean() * 100), 2))
        if "profit" in df.columns:
            aggregations["profit"] = ("profit", "sum")

        result = df.groupby("confidence_bucket", observed=False).agg(**aggregations).reset_index()
        for col in ["avg_confidence", "profit"]:
            if col in result.columns:
                result[col] = result[col].round(2)
        return result

    def profit_curve(self) -> pd.DataFrame:
        df = self.load_results()
        if df.empty or "profit" not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp")
            label_col = "timestamp"
        else:
            df = df.reset_index().rename(columns={"index": "bet_no"})
            label_col = "bet_no"

        df["cumulative_profit"] = df["profit"].fillna(0).cumsum()
        return df[[label_col, "cumulative_profit"]].dropna()

    def live_tempo_snapshot(self) -> pd.DataFrame:
        df = self.load_live()
        if df.empty:
            return pd.DataFrame()

        wanted = [
            "home", "away", "league", "minute", "score", "tempo_score", "pressure_index",
            "momentum_score_adv", "xg_pace", "advanced_signal", "advanced_market", "advanced_confidence",
        ]
        existing = [c for c in wanted if c in df.columns]
        return df[existing].copy() if existing else df.copy()

    def learning_insights(self) -> List[str]:
        insights: List[str] = []
        summary = self.performance_summary()

        if summary["bets"] == 0:
            return [
                "Brak zakończonych wyników do nauki. Bot zacznie pokazywać procenty i wykresy po zapisaniu rozliczonych typów.",
                "Aktualne picki i dane LIVE nadal mogą być analizowane, ale pełna nauka wymaga historii wyników.",
            ]

        if summary["roi_pct"] > 0:
            insights.append(f"Cały system jest aktualnie na plusie: ROI {summary['roi_pct']}% przy {summary['bets']} typach.")
        elif summary["roi_pct"] < 0:
            insights.append(f"Cały system jest aktualnie na minusie: ROI {summary['roi_pct']}%. Warto ograniczyć słabe ligi i markety.")
        else:
            insights.append(f"System jest blisko zera ROI przy {summary['bets']} typach.")

        market_perf = self.group_performance("market")
        if not market_perf.empty:
            best = market_perf.iloc[0]
            insights.append(f"Najlepszy market według danych: {best.get('market')} | ROI {best.get('roi_pct', '-')}% | typów {best.get('bets', '-') }.")

        league_perf = self.group_performance("league")
        if not league_perf.empty:
            best = league_perf.iloc[0]
            insights.append(f"Najlepsza liga według danych: {best.get('league')} | ROI {best.get('roi_pct', '-')}% | typów {best.get('bets', '-') }.")

        conf = self.confidence_accuracy()
        if not conf.empty and "real_winrate_pct" in conf.columns:
            conf_non_empty = conf[conf["bets"] > 0]
            if not conf_non_empty.empty:
                best = conf_non_empty.sort_values("real_winrate_pct", ascending=False).iloc[0]
                insights.append(f"Najlepszy zakres confidence: {best.get('confidence_bucket')} | real winrate {best.get('real_winrate_pct')}%.")

        return insights[:6]

    def save_learning_snapshot(self) -> None:
        try:
            summary = self.performance_summary()
            row = pd.DataFrame([summary])
            row["snapshot_time"] = pd.Timestamp.utcnow()
            if LEARNING_SNAPSHOT_FILE.exists():
                old = pd.read_csv(LEARNING_SNAPSHOT_FILE)
                row = pd.concat([old, row], ignore_index=True)
            row.to_csv(LEARNING_SNAPSHOT_FILE, index=False)
        except Exception:
            pass
