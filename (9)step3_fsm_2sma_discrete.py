"""Grafica la FSM y registra sus operaciones sobre datos locales con el motor común."""


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from trading.cli import main

    root = Path(__file__).resolve().parent
    defaults = ['plot', '--fsm', '--fast', '17', '--slow', '50', '--window-id', '5'] + ["--output", str(root / "results" / 'fsm_window5.png')]
    raise SystemExit(main([*defaults, *sys.argv[1:]]))
