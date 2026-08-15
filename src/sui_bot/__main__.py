import sys

try:
    from .bot import run
except RuntimeError as exc:
    print(f"SUI Bot configuration error: {exc}", file=sys.stderr)
    raise SystemExit(78) from None

run()
