from dataclasses import dataclass

@dataclass
class Viewer:
    name: str
    icon: str
    _url_template: str

    def get_viewer_url(self, url):
        return self._url_template.replace('{URL}', url)


viewers = [
    Viewer(
        'Neuroglancer', 
        'neuroglancer.png', 
        'https://neuroglancer-demo.appspot.com/#!{URL}'),
    Viewer(
        'AICS 3D Cell Viewer', 
        'aics_website-3d-cell-viewer.png', 
        'https://allen-cell-animated.github.io/website-3d-cell-viewer/?url={URL}'),
    Viewer(
        'Avivator',
        'vizarr_logo.png',
        'https://avivator.gehlenborglab.org/?image_url={URL}'),
    Viewer(
        'OME-NGFF Validator',
        'check.png',
        'https://ome.github.io/ome-ngff-validator/?source={URL}'
    )
]
