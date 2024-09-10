from enum import Enum
from typing import Iterator, Sequence, Protocol

import pathspec
from loguru import logger

from zarrcade.filestore import Filestore
from zarrcade.model import Image

class WalkResult(Enum):
    """ Result of the walk operation.
    """
    CONTAINER = 1
    """ The path is an image container according to the agent, 
        call yield_images to get the images."""
    
    CONTINUE = 0
    """ The path is not a container according to the agent, 
        continue walking with other agents, and recursively 
        search for containers."""
    
    END = -1
    """ The path is not a container, but it's something else 
        the agent recognizes and the walk should be terminated."""


class Agent(Protocol):
    """ Base class for file system agents.
    """

    def walk(self, fs: Filestore, path: str, children: list) -> WalkResult:
        """ Check if the given path is a container.

        This method should be overridden by subclasses to check if the given
        path is a container. It should use the provided path and children to
        determine if the path is a container.

        Args:
            path (str): The path to check.
            children (list): A list of child elements in the given path.

        Returns:    
            WalkResult: The result of the check.
        """
        ...

    def yield_images(self, fs: Filestore, path: str, children: list) -> Iterator[Image]:
        """ Yield images in the given path.

        This method should be overridden by subclasses to yield images found
        in the given path. It should use the provided path and children to
        determine the images to yield.

        Args:
            path (str): The path to search for images.
            children (list): A list of child elements in the given path.

        Yields:
            Iterator[Image]: An iterator of Image objects found in the path.
        """
        ...


def yield_images(fs: Filestore, 
                 agents: Sequence[Agent], 
                 path: str = '', 
                 depth: int = 0, 
                 maxdepth: int = 10) -> Iterator[Image]:
    """ Discover images in the given filestore and yield them one by one.
    """
    if depth>maxdepth: return

    for exclude_path in fs.exclude_paths:
        spec = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, exclude_path.splitlines())
        if spec.match_file(path):
            logger.trace(f"excluding {path}")
            return

    logger.trace(f"listing {path}")
    children = fs.get_children(path)
    
    container_found = False
    for agent in agents:
        result = agent.walk(fs, path, children)

        if result == WalkResult.CONTAINER:
            logger.debug(f"Found container at {path}")  
            for image in agent.yield_images(fs, path, children):
                yield image
            container_found = True
            return
        
        elif result == WalkResult.END:
            return

    if not container_found:
        # recursively search for images
        for d in [c['path'] for c in children if c['type']=='directory']:
            for image in yield_images(fs, agents,d, depth+1):
                yield image
