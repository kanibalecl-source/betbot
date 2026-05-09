# SAFE LIVE 24/7 CHANGES — BETBOT (BEZ NARUSZANIA LOGIKI I WYGLĄDU)

Te zmiany NIE zmieniają:

* wyglądu dashboardu,
* logiki typów,
* działania per-match,
* strategii,
* CSV,
* modeli,
* analizy.

Zmiany dotyczą WYŁĄCZNIE:

* stabilnego uruchamiania LIVE 24/7,
* restartów Railway,
* watchdog loop,
* healthcheck.

---

# 1. PLIK: Procfile

UTWÓRZ nowy plik:

```text
Procfile
```

Wklej:

```procfile
worker: python3 app_launcher.py
```

---

# 2. PLIK: app_launcher.py

NADPISZ cały plik:

```python
import os
import subprocess
import time
import signal
import sys

print("🚀 APP LAUNCHER START")

PORT = os.environ.get("PORT", "8080")

processes = []


def start_scheduler():
    print("🚀 START scheduler_engine.py")

    process = subprocess.Popen(
        ["python3", "scheduler_engine.py"]
    )

    print("✅ scheduler_engine.py STARTED")

    return process



def start_dashboard():
    print("🚀 START dashboard_streamlit.py")

    process = subprocess.Popen(
        [
            "streamlit",
            "run",
            "dashboard_streamlit.py",
            "--server.port",
            str(PORT),
            "--server.address",
            "0.0.0.0",
            "--server.headless",
            "true",
        ]
    )

    print("✅ dashboard_streamlit.py STARTED")

    return process



def shutdown(*args):
    print("🛑 SHUTDOWN START")

    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass

    print("✅ SHUTDOWN COMPLETE")

    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


while True:
    try:
        scheduler_process = start_scheduler()
        dashboard_process = start_dashboard()

        processes = [scheduler_process, dashboard_process]

        while True:
            scheduler_alive = scheduler_process.poll() is None
            dashboard_alive = dashboard_process.poll() is None

            print(
                f"💓 HEARTBEAT | scheduler={scheduler_alive} | dashboard={dashboard_alive}"
            )

            if not scheduler_alive:
                print("❌ scheduler_engine.py CRASHED -> RESTART")
                scheduler_process = start_scheduler()
                processes[0] = scheduler_process

            if not dashboard_alive:
                print("❌ dashboard_streamlit.py CRASHED -> RESTART")
                dashboard_process = start_dashboard()
                processes[1] = dashboard_process

            time.sleep(30)

    except Exception as e:
        print(f"❌ APP LAUNCHER ERROR: {e}")
        time.sleep(15)
```

---

# 3. PLIK: app.py

NADPISZ TYLKO końcówkę pliku.

ZNAJDŹ:

```python
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=False)
```

ZAMIEŃ NA:

```python
if __name__ == "__main__":
    init_db()

    port = int(os.environ.get("PORT", 8080))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
```

ORAZ NA GÓRZE PLIKU DODAJ:

```python
import os
```

---

# 4. PLIK: requirements.txt

DOPISZ NA KOŃCU:

```text
flask
gunicorn
```

Finalnie:

```text
pandas
requests
python-dotenv
streamlit
numpy
flask
gunicorn
```

---

# 5. PLIK: runtime.txt

UTWÓRZ:

```text
runtime.txt
```

Wklej:

```text
python-3.11.9
```

---

# 6. PLIK: railway.json

UTWÓRZ:

```text
railway.json
```

Wklej:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

---

# 7. RAILWAY VARIABLES

W Railway → Variables dodaj:

```env
API_FOOTBALL_KEY=...
ODDS_API_KEY=...
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
ENV=production
```

---

# 8. RAILWAY SETTINGS

## Start Command

USTAW:

```bash
python3 app_launcher.py
```

---

## Auto Deploy

USTAW:

```text
ON
```

---

# 9. CO TE ZMIANY DAJĄ

✅ LIVE 24/7
✅ auto restart po crashu
✅ watchdog
✅ stabilny Streamlit
✅ stabilny scheduler
✅ kompatybilność Railway
✅ brak zmian UI
✅ brak zmian logiki
✅ brak zmian strategii
✅ brak zmian typów

---

# 10. DEPLOY

Po podmianie plików:

```bash
git add .
git commit -m "LIVE 24/7 SAFE PATCH"
git push
```

Railway zrobi automatyczny deploy.

---

# 11. GOTOWE

Po deploy:

* bot działa LIVE,
* dashboard działa,
* scheduler działa,
* Railway restartuje po błędach,
* nic nie zmienia obecnego działania bota.
