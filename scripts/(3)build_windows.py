"""Define ventanas locales con warmup y purga train/test usando el motor común."""


if __name__ == "__main__":
    import sys
    from trading.cli import main

    defaults = ['windows']
    raise SystemExit(main([*defaults, *sys.argv[1:]]))
