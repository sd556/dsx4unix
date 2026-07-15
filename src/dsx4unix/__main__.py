"""CLI entry point for dsx4unix."""

from __future__ import annotations
import argparse
import logging
import signal
import sys
from pathlib import Path

from dsx4unix.config.loader import list_profiles, load_config, load_profile
from dsx4unix.engine import Engine


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dsx4unix",
        description="Racing telemetry → DualSense adaptive triggers on Linux",
    )
    parser.add_argument(
        "--profile",
        choices=list_profiles(),
        default="forza",
        help="Built-in profile to use (default: forza)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Custom YAML config file (overrides --profile)",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available profiles and exit",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.list_profiles:
        print("Available profiles:")
        for name in list_profiles():
            p = load_profile(name)
            print(f"  {name:10s}  {p.name} (telemetry port {p.telemetry_port})")
        return

    # Load profile
    if args.config:
        profile = load_config(args.config)
        if args.verbose:
            profile.verbose = True
    else:
        profile = load_profile(args.profile)
        if args.verbose:
            profile.verbose = True

    # Setup logging
    level = logging.DEBUG if profile.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Create engine
    engine = Engine(profile)

    # Signal handling
    def _shutdown(sig: int, frame: object) -> None:
        logger = logging.getLogger(__name__)
        logger.info("Signal %d received, shutting down...", sig)
        engine.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Run
    try:
        engine.run()
    except KeyboardInterrupt:
        engine.stop()


if __name__ == "__main__":
    main()
