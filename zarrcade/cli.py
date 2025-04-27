import click

class DotDict:
    def __init__(self, dictionary):
        for key, value in dictionary.items():
            setattr(self, key, value)
            
@click.group()
def cli():
    pass
@cli.command()
@click.argument('settings_path', type=str, required=True)
@click.option('--skip-image-load', is_flag=True, default=False,
              help="Skip loading images from the data directory.")
@click.option('--skip-thumbnail-creation', is_flag=True, default=False,
              help="Skip creating thumbnails if they do not already exist.")
@click.option('--only-with-metadata', is_flag=True, default=False,
              help="Only load images for which metadata is provided?")
@click.option('-x', '--no-aux', is_flag=True, default=False,
              help="Don't create auxiliary images or thumbnails.")
@click.option('-a', '--aux-path', type=str, default="static/.zarrcade",
              help='Local path to the folder for auxiliary images.')
@click.option('--aux-image-name', type=str, default='thumbnail.png',
              help='Filename of the main auxiliary image in the auxiliary image folder.')
@click.option('--thumbnail-name', type=str, default='thumbnail.jpg',
              help='Filename of the downsampled thumbnail image in the auxiliary image folder.')
@click.option('--p-lower', type=int, default=0,
              help='Lower percentile for thumbnail brightness adjustment.')
@click.option('--p-upper', type=int, default=90,
              help='Upper percentile for thumbnail brightness adjustment.')
def load(settings_path, skip_image_load, skip_thumbnail_creation, only_with_metadata, no_aux, aux_path, aux_image_name, thumbnail_name, p_lower, p_upper):
    """Import data into the Zarrcade database by walking a filesystem and discovering Zarrs.
    Optionally imports metadata and 2d thumbnails."""
    args = DotDict({
        'skip_image_load': skip_image_load,
        'skip_thumbnail_creation': skip_thumbnail_creation,
        'only_with_metadata': only_with_metadata,
        'no_aux': no_aux,
        'aux_path': aux_path,
        'aux_image_name': aux_image_name,
        'thumbnail_name': thumbnail_name,
        'p_lower': p_lower,
        'p_upper': p_upper,
    })
    from zarrcade.load import load
    load(settings_path, args)


@cli.command()
@click.option('--host', type=str, default='0.0.0.0', help='Host address to bind the server to.')
@click.option('--port', type=int, default=8000, help='Port to run the server on.')
@click.option('--reload', is_flag=True, default=False, help='Reload the server on code changes.')
@click.option('--ssl-keyfile', type=str, help='Path to the SSL key file.')
@click.option('--ssl-certfile', type=str, help='Path to the SSL certificate file.')
def start(host, port, reload, ssl_keyfile, ssl_certfile):
    click.echo(f'Starting the server on {host}:{port}')
    import uvicorn
    # For reload to work, we need to pass the application as an import string
    uvicorn.run("zarrcade.serve:app", 
                host=host, 
                port=port, 
                reload=reload, 
                ssl_keyfile=ssl_keyfile, 
                ssl_certfile=ssl_certfile)
    
@cli.command()
@click.option('--no-coverage', is_flag=True, default=False, help='Do not include coverage report.')
@click.option('--print-warnings', is_flag=True, default=False, help='Print deprecationwarnings during testing.')
def test(no_coverage, print_warnings):
    """Run tests with coverage report."""
    click.echo('Running tests with coverage report...')
    import subprocess
    cmd = ["python", "-m", "pytest"]
    if not no_coverage:
        cmd.append("--cov=zarrcade")
        cmd.append("--cov-report=html")
    if not print_warnings:
        cmd.append("-W")
        cmd.append("ignore::DeprecationWarning")
    subprocess.run(cmd)
