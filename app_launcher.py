import subprocess
import webbrowser
import time
import socket


def wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


# bot w tle
subprocess.Popen(
    ["python", "main.py", "loop"],
    creationflags=subprocess.CREATE_NO_WINDOW
)

# dashboard w tle
subprocess.Popen(
    ["python", "-m", "streamlit", "run", "dashboard.py"],
    creationflags=subprocess.CREATE_NO_WINDOW
)

# czekaj aż Streamlit naprawdę zacznie nasłuchiwać
ready = wait_for_port("127.0.0.1", 8501, timeout=40)

if ready:
    webbrowser.open("http://127.0.0.1:8501")
else:
    # awaryjnie spróbuj otworzyć mimo wszystko
    subprocess.Popen(
        ["cmd", "/c", "start", "", "http://127.0.0.1:8501"],
        creationflags=subprocess.CREATE_NO_WINDOW
    )