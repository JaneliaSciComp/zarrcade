import click


def get_db():
    from zarrcade.database import Database
    from zarrcade.settings import get_settings
    settings = get_settings()
    db_url = str(settings.database.url)
    db = Database(db_url)
    return db

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
    """Load data into a collection.
    
    Walks a filesystem and discovers Zarrs, or loads images from a metadata file.
    Optionally imports metadata and generates2d thumbnails."""
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
    """Start the Zarrcade server."""
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


@cli.group()
def collection():
    """Commands for managing collections."""
    pass


@collection.command(name="list")
def list_collections():
    """List all collections in the database."""
    db = get_db()
    collections = db.get_collections()
    if not collections:
        click.echo("No collections found.")
        return
    
    click.echo(f"Found {len(collections)} collection(s):")
    for collection in collections:
        click.echo(f"- id: {collection.id}")
        click.echo(f"  name: {collection.name}")
        click.echo(f"  settings_path: {collection.settings_path}")


@collection.command(name="get")
@click.option('--id', type=int, required=True, help='ID of the collection to retrieve.')
def get_collection(id):
    """Get details of a specific collection."""
    collection = get_db().get_collection(id)
    
    if not collection:
        click.echo(f"Collection with id '{id}' does not exist.")
        return
    
    click.echo(f"id: {collection.id}")
    click.echo(f"name: {collection.name}")
    click.echo(f"settings_path: {collection.settings_path}")


@collection.command(name="update")
@click.option('--id', type=int, required=True, help='ID of the collection to update.')
@click.option('--name', type=str, help='New name for the collection.')
@click.option('--settings-path', type=str, help='New settings path for the collection.')
def update_collection(id, name, settings_path):
    """Update a collection's name or settings path."""
    db = get_db()
    collection = db.get_collection(id)
    
    if not collection:
        click.echo(f"Collection with id '{id}' does not exist.")
        return
    
    if not name and not settings_path:
        click.echo("No changes specified. Use --name or --settings-path to specify changes.")
        return
    
    with db.sessionmaker() as session:
        # Attach the collection to the session to ensure it's tracked for updates
        from zarrcade.database import DBCollection
        collection = session.query(DBCollection).filter_by(id=id).first()
        if not collection:
            click.echo(f"Collection with id '{id}' not found in database.")
            return
        try:
            if name:
                # Check if the new name already exists
                if name != collection.name and any(c.name == name for c in db.get_collections()):
                    click.echo(f"Collection with name '{name}' already exists.")
                    return
                
                collection.name = name
                click.echo(f"Collection[id={id}]: name updated to '{name}'")
            
            if settings_path:
                collection.settings_path = settings_path
                click.echo(f"Collection[id={id}]: settings_path updated to '{settings_path}'")
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            click.echo(f"Error updating collection: {str(e)}")


@collection.command(name="delete")
@click.option('--id', type=int, required=True, help='ID of the collection to delete.')
@click.option('--force', is_flag=True, default=False, help='Force deletion without confirmation.')
def delete_collection(id, force):
    """Delete a collection and all its associated data."""
    db = get_db()
    
    # Check if collection exists
    collection = db.get_collection(id)
    
    if not collection:
        click.echo(f"Collection[id={id}] does not exist.")
        return
    
    if not force:
        confirm = click.confirm(f"Are you sure you want to delete collection '{collection.name}'? This will remove all associated image metadata and cannot be undone.")
        if not confirm:
            click.echo("Operation cancelled.")
            return
    
    try:
        db.delete_collection(collection.name)
        click.echo(f"Collection[id={id}] has been deleted.")
    except Exception as e:
        click.echo(f"Error deleting collection: {str(e)}")


@collection.command(name="clear-aux")
@click.option('--id', type=int, required=True, help='ID of the collection to clear auxiliary images for.')
@click.option('--force', is_flag=True, default=False, help='Force clearing without confirmation.')
def clear_aux_images(id, force):
    """Clear all thumbnails and auxiliary images for a collection."""
    db = get_db()
    
    # Check if collection exists
    collection = db.get_collection(id)
    
    if not collection:
        click.echo(f"Collection[id={id}] does not exist.")
        return
    
    if not force:
        confirm = click.confirm(f"Are you sure you want to clear all thumbnails and auxiliary images for collection '{collection.name}'? This cannot be undone.")
        if not confirm:
            click.echo("Operation cancelled.")
            return
    
    try:
        from zarrcade.database import DBImageMetadata
        with db.sessionmaker() as session:
            # Get all image metadata for the collection
            metadata_records = session.query(DBImageMetadata).filter(DBImageMetadata.collection_id == collection.id).all()
            count = 0
            
            for metadata in metadata_records:
                updated = False
                
                if metadata.thumbnail_path:
                    metadata.thumbnail_path = None
                    updated = True
                
                if metadata.aux_image_path:
                    metadata.aux_image_path = None
                    updated = True
                
                if updated:
                    count += 1
            
            session.commit()
            click.echo(f"Cleared auxiliary images for {count} records in collection '{collection.name}'.")
    except Exception as e:
        click.echo(f"Error clearing auxiliary images: {str(e)}")


if __name__ == "__main__":
    cli()
