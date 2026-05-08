# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([

    "🚨 LIVE",
    "⚽ PREMATCH",
    "📊 ANALYTICS",
    "🕘 HISTORY",
    "🏆 RANKING",
    "🔔 ALERTS"

])

# =====================================================
# LIVE
# =====================================================

with tab1:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("LIVE SIGNALS")

    st.caption("AKTUALIZOWANE CO 60 SEKUND")

    st.markdown('</div>', unsafe_allow_html=True)

    if live_df.empty:

        st.warning("Brak aktywnych meczów LIVE.")

    else:

        st.table(live_df)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("CASHOUT AI GUIDE")

    st.markdown("""

    <div class="live-card green">
        HOLD POSITION — Wysoka presja i momentum.
    </div>

    <div class="live-card yellow">
        PARTIAL CASHOUT — Spadający confidence.
    </div>

    <div class="live-card red">
        FULL CASHOUT — Niski momentum.
    </div>

    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# PREMATCH
# =====================================================

with tab2:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("PREMATCH PICKS")

    if prematch_df.empty:

        st.warning("Brak danych PREMATCH")

    else:

        columns = [

            "data",
            "liga",
            "mecz",
            "market",
            "typ",
            "kurs_buk",
            "kurs_model",
            "kurs_bota",
            "prawd_model",
            "prawd_rynek",
            "prawd_final",
            "edge",
            "ev",
            "kelly_full",
            "kelly_25",
            "home_xg",
            "away_xg",
            "marza_sum",
            "marza_%",
            "status"

        ]

        existing = [c for c in columns if c in prematch_df.columns]

        st.table(
            prematch_df[existing]
        )

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# ANALYTICS
# =====================================================

with tab3:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("ANALYTICS ENGINE")

    st.metric("ROI", "+24.8%")
    st.metric("WIN RATE", "62.8%")
    st.metric("AI EDGE", "+13.4%")

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# HISTORY
# =====================================================

with tab4:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("HISTORY ENGINE")

    st.info("Historia zakładów będzie dostępna po wdrożeniu Settlement Engine.")

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# RANKING
# =====================================================

with tab5:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("RANKING ENGINE")

    st.info("TOP VALUE PICKS coming soon.")

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# ALERTS
# =====================================================

with tab6:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("ALERT ENGINE")

    st.info("Alerty AI będą dostępne po wdrożeniu Notification Engine.")

    st.markdown('</div>', unsafe_allow_html=True)
