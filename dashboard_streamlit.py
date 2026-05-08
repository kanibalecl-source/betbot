st.markdown(
    """
    <div class="panel">

        <h2>
            CASHOUT AI GUIDE
        </h2>

        <div style="
            margin-top:14px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(88,255,47,0.35);
            background:rgba(88,255,47,0.08);
            margin-bottom:14px;
        ">

            <div class="badge green">
                HOLD POSITION
            </div>

            <p style="color:#cfd4d8;">
                Wysoka presja i momentum. Trzymaj zakład.
            </p>

        </div>

        <div style="
            margin-top:14px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(255,210,26,0.35);
            background:rgba(255,210,26,0.08);
            margin-bottom:14px;
        ">

            <div class="badge yellow">
                PARTIAL CASHOUT
            </div>

            <p style="color:#cfd4d8;">
                Spadający confidence. Rozważ częściowe wyjście.
            </p>

        </div>

        <div style="
            margin-top:14px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(255,59,48,0.35);
            background:rgba(255,59,48,0.08);
        ">

            <div class="badge red">
                FULL CASHOUT
            </div>

            <p style="color:#cfd4d8;">
                Niski momentum i presja. Wyjdź z zakładu.
            </p>

        </div>

    </div>
    """,
    unsafe_allow_html=True
)
