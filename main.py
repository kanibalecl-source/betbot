import sys

from bot import run_bot


def main():
    command = sys.argv[1].lower() if len(sys.argv) > 1 else "once"

    if command == "once":
        run_bot()
        return

    if command == "loop":
        from bot_loop import main as loop_main

        loop_main()
        return

    raise SystemExit("Uzycie: python main.py once | loop")


if __name__ == "__main__":
    main()
