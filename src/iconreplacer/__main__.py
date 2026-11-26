"""Entry point: ``python -m iconreplacer``."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from iconreplacer.cli import parse_args

    options = parse_args(argv)  # handles --version before any Qt import

    if options.shell_action:
        from iconreplacer.cli import run_shell_action

        return run_shell_action(options.shell_action)

    from iconreplacer.app import run

    return run(options)


if __name__ == "__main__":
    sys.exit(main())
