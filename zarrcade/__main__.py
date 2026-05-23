"""CLI entry point for zarrcade."""

import click
from loguru import logger

from .commands.discover import discover
from .commands.embed_thumbnails import embed
from .commands.generate_mips import mips
from .commands.thumbnails import thumbnails


@click.group()
@click.version_option()
def cli():
    """Zarrcade CLI - Tools for OME-Zarr image processing."""
    pass


cli.add_command(discover)
cli.add_command(embed)
cli.add_command(mips)
cli.add_command(thumbnails)


if __name__ == "__main__":
    cli()
