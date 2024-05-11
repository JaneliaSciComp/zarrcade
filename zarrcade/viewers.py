from dataclasses import dataclass

@dataclass
class Viewer:
    name: str
    icon: str
    _url_template: str

    def get_viewer_url(self, url):
        return self._url_template.replace('{URL}', url)


Neuroglancer = Viewer(
    'Neuroglancer', 
    'neuroglancer.png', 
    'https://neuroglancer-demo.appspot.com/#!{URL}')

AICS3DCellViewer = Viewer(
    'AICS 3D Cell Viewer', 
    'aics_website-3d-cell-viewer.png', 
    'https://allen-cell-animated.github.io/website-3d-cell-viewer/?url={URL}')

Avivator = Viewer(
    'Avivator',
    'vizarr_logo.png',
    'https://avivator.gehlenborglab.org/?image_url={URL}')
    
Validator = Viewer(
    'OME-NGFF Validator',
    'check.png',
    'https://ome.github.io/ome-ngff-validator/?source={URL}')

viewers = [
    Neuroglancer,
    AICS3DCellViewer,
    Avivator,
    Validator
]
