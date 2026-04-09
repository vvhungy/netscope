"""Allow running as python -m netscope."""

import sys


def main() -> int:
    """Route to CLI or GUI based on arguments."""
    # If there are command-line arguments beyond the module name,
    # or if we can't import PyQt6, use CLI
    args = sys.argv[1:]

    if args:
        # Has arguments - likely CLI usage
        from .cli import main as cli_main
        return cli_main()

    # No arguments - try GUI
    try:
        from .main import main as gui_main
        return gui_main()
    except ImportError as e:
        # PyQt6 not available, fall back to CLI
        print(f"GUI not available ({e}), using CLI mode.", file=sys.stderr)
        print("Run with --help for usage.", file=sys.stderr)
        from .cli import main as cli_main
        return cli_main()


if __name__ == "__main__":
    sys.exit(main())
