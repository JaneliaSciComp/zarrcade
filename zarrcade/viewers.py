from dataclasses import dataclass
from enum import Enum


@dataclass
class ViewerInfo:
    name: str
    icon: str
    _url_template: str

    def get_viewer_url(self, url):
        return self._url_template.replace('{URL}', url)


class Viewer(Enum):
    """Enum for supported viewers"""

    NEUROGLANCER = ViewerInfo(
        'Neuroglancer',
        'neuroglancer.png',
        'https://neuroglancer-demo.appspot.com/#!{URL}'
    )

    VALIDATOR = ViewerInfo(
        'OME-NGFF Validator',
        'check.png',
        'https://ome.github.io/ome-ngff-validator/?source={URL}'
    )

    VOLE = ViewerInfo(
        'Vol-E',
        'aics_website-3d-cell-viewer.png',
        'https://volumeviewer.allencell.org/viewer?url={URL}'
    )

    AVIVATOR = ViewerInfo(
        'Avivator',
        'vizarr_logo.png',
        'https://avivator.gehlenborglab.org/?image_url={URL}'
    )

    BIONGFF = ViewerInfo(
        'BioNGFF',
        'vizarr_logo.png',
        'https://biongff.github.io/biongff-viewer/?source={URL}'
    )

    @property
    def name(self) -> str:
        return self.value.name

    @property
    def icon(self) -> str:
        return self.value.icon

    def get_viewer_url(self, url: str) -> str:
        """Public method: generate the URL for this viewer."""
        return self.value.get_viewer_url(url)

    @classmethod
    def from_string(cls, s: str) -> "Viewer":
        """
        Resolve a viewer by enum name (case-insensitive).
        Raises ValueError if not found.
        """
        s_norm = s.strip().lower()
        for v in cls:
            if v.name.lower() == s_norm:
                return v
        raise ValueError(f"Unknown viewer: {s}")


def get_viewer(viewer_name: str):
    return Viewer.from_string(viewer_name)

def get_viewers():
    return list(Viewer)