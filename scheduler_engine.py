import time
from datetime import datetime
from bot import run_prematch, run_live, run_settlement, capture_closing_snapshot_for_soon_matches
from notifier import send_picks, send_live
from risk import get_mode

def loop():
    last_prematch_hour = None
    last_settlement_hour = None
    last_closing_check_minute = None
    last_live_mark = None

    while True:
        now = datetime.now()
        mode = get_mode()
        print(f"[{now}] MODE: {mode}")

        if mode == "STOP":
            print("System in STOP mode. Sleeping 60 min.")
            time.sleep(3600)
            continue

        if last_prematch_hour != now.hour:
            prematch_df = run_prematch()
            if prematch_df is not None and not prematch_df.empty:
                send_picks(prematch_df)
            last_prematch_hour = now.hour

        live_mark = (now.hour, now.minute // 5)
        if live_mark != last_live_mark:
            live_df = run_live()
            if live_df is not None and not live_df.empty:
                send_live(live_df)
            last_live_mark = live_mark

        if now.minute % 10 == 0 and last_closing_check_minute != now.minute:
            capture_closing_snapshot_for_soon_matches()
            last_closing_check_minute = now.minute

        if now.hour % 2 == 0 and last_settlement_hour != now.hour:
            run_settlement()
            last_settlement_hour = now.hour

        time.sleep(60)
