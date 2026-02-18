"""CLI entry point for zarrcade."""

import click
from loguru import logger

from .commands.discover import discover
from .commands.generate_mips import mips


@click.group()
@click.version_option()
def cli():
    """Zarrcade CLI - Tools for OME-Zarr image processing."""
    pass


cli.add_command(discover)
cli.add_command(mips)


if __name__ == "__main__":
    cli()
