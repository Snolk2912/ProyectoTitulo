"""Audita un CSV local con el validador común, sin descargas."""


if __name__ == "__main__":
    import sys
    from trading.cli import main

    defaults = ['audit']
    raise SystemExit(main([*defaults, *sys.argv[1:]]))
