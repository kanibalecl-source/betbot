with live_tab:

    with st.container(border=True):
        st.header("🟢 LIVE SIGNALS")
        st.caption("AKTUALIZOWANE CO 60 SEKUND")

    if live_df.empty:

        st.warning("Brak danych LIVE")

    else:

        live_columns = [
            "home",
            "away",
            "league",
            "minute",
            "score",
            "pressure",
            "momentum",
            "signal",
            "confidence",
            "odds",
            "value",
            "ev",
            "cashout",
            "stake",
            "risk",
            "status"
        ]

        live_view = only_existing_columns(
            live_df,
            live_columns
        )

        for _, row in live_view.iterrows():

            with st.container(border=True):

                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:

                    home = row.get("home", "")
                    away = row.get("away", "")
                    league = row.get("league", "")

                    st.subheader(f"{home} vs {away}")

                    st.caption(f"{league}")

                with col2:

                    st.metric(
                        "ODDS",
                        row.get("odds", "-")
                    )

                with col3:

                    st.metric(
                        "CONF",
                        row.get("confidence", "-")
                    )

                st.write(
                    f"📡 SIGNAL: {row.get('signal', '-')}"
                )

                st.write(
                    f"⚡ MOMENTUM: {row.get('momentum', '-')}"
                )

                st.write(
                    f"🔥 PRESSURE: {row.get('pressure', '-')}"
                )

                st.write(
                    f"💰 VALUE: {row.get('value', '-')}"
                )

                st.write(
                    f"📈 EV: {row.get('ev', '-')}"
                )

                st.write(
                    f"⏱️ MINUTE: {row.get('minute', '-')}"
                )

                st.write(
                    f"⚽ SCORE: {row.get('score', '-')}"
                )

                st.write(
                    f"🟢 STATUS: {row.get('status', '-')}"
                )

                st.divider()

    with st.container(border=True):

        st.header("CASHOUT AI GUIDE")

        st.success(
            "HOLD POSITION — Wysoka presja i momentum. Trzymaj zakład."
        )

        st.warning(
            "PARTIAL CASHOUT — Spadający confidence. Rozważ częściowe wyjście."
        )

        st.error(
            "FULL CASHOUT — Niski momentum i presja. Wyjdź z zakładu."
        )
