"""Grafica la SMA de un CSV local con el cálculo causal común, sin descargas."""


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from trading.cli import main

    root = Path(__file__).resolve().parent.parent
    defaults = ['plot', '--single', '--fast', '50', '--slow', '200', '--window-id', '5'] + ["--output", str(root / "results" / 'sma50_window5.png')]
    raise SystemExit(main([*defaults, *sys.argv[1:]]))
