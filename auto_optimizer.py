import pandas as pd


class AutoOptimizer:

    def best_leagues(
        self,
        results_df,
        min_bets=30
    ):

        if results_df.empty or "league" not in results_df.columns or "profit" not in results_df.columns:
            return pd.DataFrame()

        grouped = (
            results_df.groupby("league")
            .agg(
                bets=("profit", "count"),
                profit=("profit", "sum"),
                avg_profit=("profit", "mean")
            )
            .reset_index()
        )

        grouped = grouped[grouped["bets"] >= min_bets]

        return grouped.sort_values("profit", ascending=False)


    def best_markets(
        self,
        results_df,
        min_bets=30
    ):

        if results_df.empty or "market" not in results_df.columns or "profit" not in results_df.columns:
            return pd.DataFrame()

        grouped = (
            results_df.groupby("market")
            .agg(
                bets=("profit", "count"),
                profit=("profit", "sum"),
                avg_profit=("profit", "mean")
            )
            .reset_index()
        )

        grouped = grouped[grouped["bets"] >= min_bets]

        return grouped.sort_values("profit", ascending=False)


    def recommended_thresholds(
        self,
        results_df
    ):

        if results_df.empty or "confidence" not in results_df.columns or "profit" not in results_df.columns:
            return {
                "min_confidence": 65,
                "min_ev": 5
            }

        df = results_df.copy()

        df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
        df["ev"] = pd.to_numeric(df["ev"], errors="coerce")
        df["profit"] = pd.to_numeric(df["profit"], errors="coerce")

        best = {
            "min_confidence": 65,
            "min_ev": 5,
            "profit": -999999
        }

        for conf in [55, 60, 65, 70, 75, 80]:
            for ev in [2, 5, 8, 10, 12]:
                sample = df[
                    (df["confidence"] >= conf) &
                    (df["ev"] >= ev)
                ]

                if len(sample) < 20:
                    continue

                profit = sample["profit"].sum()

                if profit > best["profit"]:
                    best = {
                        "min_confidence": conf,
                        "min_ev": ev,
                        "profit": round(float(profit), 2)
                    }

        return best
