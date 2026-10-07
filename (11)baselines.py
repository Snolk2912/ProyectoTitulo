"""Compara estrategias sobre un CSV local con el motor común, sin descargas."""


if __name__ == "__main__":
    import sys
    from trading.cli import main

    defaults = ['baselines']
    raise SystemExit(main([*defaults, *sys.argv[1:]]))
