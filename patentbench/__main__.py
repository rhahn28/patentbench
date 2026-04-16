"""Allow running PatentBench as: python -m patentbench"""
from __future__ import annotations


def main() -> None:
    from scripts.run_benchmark import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
