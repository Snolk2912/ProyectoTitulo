"""Simula la configuración publicada sobre datos locales con el motor común."""


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from trading.cli import main

    root = Path(__file__).resolve().parent
    defaults = ['simulate', '--window-id', '16'] + ["--output", str(root / "results" / 'trades_window16.json')]
    raise SystemExit(main([*defaults, *sys.argv[1:]]))
