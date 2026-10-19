"""Command-line entry points, with credentials kept outside command arguments."""
import argparse
from .analysis import run_analysis


def main():
    parser = argparse.ArgumentParser(prog="methane-hunter")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Verify frozen inputs, then run the regional analysis")
    analyze.add_argument("--root", default=".")
    analyze.add_argument("--limit", type=int, help="Explicit provisional numeric validation run")
    sub.add_parser("fetch-nasa", help="Download frozen NASA inputs using hidden token entry")
    args = parser.parse_args()
    if args.command == "analyze":
        run_analysis(args.root, limit=args.limit)
    else:
        from .nasa import fetch_nasa_selected
        fetch_nasa_selected()


if __name__ == "__main__":
    main()

