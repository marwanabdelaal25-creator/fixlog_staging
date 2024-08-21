"""Allow `python -m fixlog` invocation."""

from fixlog.cli import main

__doc__ = """
Entry point for the fixlog CLI.

Examples:
  python -m fixlog init
  python -m fixlog dwelling-add "Monstera" --contractor monstera-deliciosa
  python -m fixlog service <dwelling-id> --amount 250ml
  python -m fixlog schedule --week
  python -m fixlog export homestead.json

Environment:
  FIXLOG_HOME  Directory for default homestead.json (default: ~/.fixlog/)
"""

if __name__ == "__main__":
    raise SystemExit(main())
