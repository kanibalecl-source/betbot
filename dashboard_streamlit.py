# =========================
# GPT TAB FOR STREAMLIT
# =========================

import streamlit as st

# =====================================
# TABS
# =====================================

tabs = st.tabs([
    "LIVE",
    "PREMATCH",
    "AI",
    "ANALYTICS",
    "🤖 GPT"
])

# =====================================
# LIVE
# =====================================

with tabs[0]:
    st.title("LIVE")

# =====================================
# PREMATCH
# =====================================

with tabs[1]:
    st.title("PREMATCH")

# =====================================
# AI
# =====================================

with tabs[2]:
    st.title("AI")

# =====================================
# ANALYTICS
# =====================================

with tabs[3]:
    st.title("ANALYTICS")

# =====================================
# GPT ANALYSIS
# =====================================

with tabs[4]:

    st.title("🤖 GPT ANALYSIS")

    st.success("GPT ACTIVE")

    st.markdown("""
# Arsenal vs Chelsea

✅ PLAY  
📈 Confidence: 81%  
💎 Value: HIGH  
⚠️ Risk: MEDIUM  

---

## 🧠 GPT ANALIZA

Arsenal prezentuje bardzo dobrą formę u siebie i regularnie tworzy dużą liczbę sytuacji bramkowych.

Chelsea ma wyraźne problemy defensywne w meczach wyjazdowych i często traci gole po szybkich przejściach rywali.

Model GPT ocenia zakład BTTS jako korzystny względem aktualnego kursu bukmacherskiego.

---

# 💎 SAFE AKO

- Arsenal vs Chelsea — BTTS
- Milan vs Roma — Over 1.5

---

# 📊 OCENA GPT

| Parametr | Ocena |
|---|---|
| Value | HIGH |
| Confidence | 81% |
| Ryzyko | MEDIUM |
| AKO | TAK |

""")
