# Zarrcade

[![CI](https://github.com/JaneliaSciComp/zarrcade/actions/workflows/ci.yml/badge.svg)](https://github.com/JaneliaSciComp/zarrcade/actions/workflows/ci.yml)

Zarrcade makes it easy to generate simple client-side webapps for browsing, searching, and visualizing collections of [OME-NGFF](https://github.com/ome/ngff) (i.e. OME-Zarr) images.

<img alt="Zarrcade screenshot" src="https://github.com/user-attachments/assets/57895e8f-b427-43d3-bd81-bae2acb449a7" />

## Features

* Automatic discovery of OME-Zarr images on local filesystems and [S3-compatible storage](https://filesystem-spec.readthedocs.io/en/latest/api.html#other-known-implementations)
* MIP (Maximum Intensity Projection) and thumbnail generation with advanced contrast adjustment
* Optional embedding of thumbnails into the zarr itself via the [thumbnails convention](https://github.com/clbarnes/zarr-convention-thumbnails)
* Static web gallery with full-text search and filterable metadata -- no backend required
* One-click viewing in [Neuroglancer](https://github.com/google/neuroglancer), [Avivator](https://github.com/hms-dbmi/viv), and other OME-Zarr-compatible viewers
* Customizable branding, title templates, and viewer configuration
* URL-shareable state (search terms, filters, pagination, detail view)


## Architecture

Zarrcade has two independent components:

| Component | Purpose | Technology |
|-----------|---------|------------|
| **CLI** (`zarrcade/`) | Discover zarrs, generate MIPs/thumbnails, embed thumbnails into zarrs | Python (Click, zarr, fsspec, microfilm) |
| **Web SPA** (`web/`) | Display searchable image gallery from CSV data | React + TypeScript (Vite, PapaParse, Pico CSS) |

The CLI produces CSV files and thumbnail images. The SPA reads those CSV files directly in the browser -- there is no backend server or database. The SPA builds to static HTML/JS/CSS that can be served from any static file host.

```
┌─────────────┐         ┌─────────┐         ┌────────────┐
│  OME-Zarr   │──CLI───>│  CSV +  │──HTTP──>│  React SPA │
│  Images     │         │  MIPs   │         │  (browser) │
└─────────────┘         └─────────┘         └────────────┘
```


## Quick Start

### Prerequisites

* [Pixi](https://pixi.sh/latest/) (for the CLI)
* [Node.js](https://nodejs.org/) 20+ (for the web SPA)

### Example 1: Fly-eFISH

Discover OME-Zarr images from S3 and view them in the gallery:

```bash
# Clone and set up the CLI
git clone https://github.com/JaneliaSciComp/zarrcade.git
cd zarrcade
pixi install

# Discover zarr containers (or use the pre-made CSV in examples/)
pixi run zarrcade discover s3://janelia-data-examples/fly-efish \
    -o examples/flyefish.csv --include-metadata

# Generate thumbnails
pixi run zarrcade mips --input-csv examples/flyefish.csv \
    -o examples/thumbnails --output-csv examples/flyefish-with-thumbs.csv

# (optional) Embed those thumbnails into the zarrs so the SPA can find them
# without a thumbnail column
pixi run zarrcade embed --input-csv examples/flyefish-with-thumbs.csv \
    --zarr-base-url https://janelia-data-examples.s3.amazonaws.com/fly-efish

# Serve the gallery locally
cd web
cp ../examples/config-flyefish.json public/config.local.json
npm install
npm run dev
```

### Example 2: OpenOrganelle

This example uses pre-existing thumbnail URLs, so no MIP generation is needed:

```bash
cd web
cp ../examples/config-openorganelle.json public/config.local.json
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) to browse the gallery.


## CLI Usage

The CLI has four commands:

| Command | What it does |
|---------|--------------|
| **discover** | Walk a directory tree (local or S3) for OME-Zarr containers and emit a CSV manifest. |
| **mips** | Generate Maximum Intensity Projection images and small thumbnails for each zarr. |
| **thumbnails** | Resize an existing folder of raster images into smaller JPEGs. |
| **embed** | Write existing thumbnail JPEGs into their zarr containers via the [thumbnails convention](https://github.com/clbarnes/zarr-convention-thumbnails), so the SPA can read them without a separate CSV column. |

Run all commands from the repo root.

### Discover OME-Zarr Containers

Scan a directory tree for OME-Zarr containers and output their paths and metadata as CSV:

```bash
pixi run zarrcade discover /path/to/zarrs -o images.csv

# Include image metadata (dimensions, channels, compression, etc.)
pixi run zarrcade discover /path/to/zarrs -o images.csv --include-metadata

# Discover from S3 with a base URL for web access
pixi run zarrcade discover s3://bucket/zarrs -o images.csv \
    --base-url https://bucket.s3.amazonaws.com/zarrs

# Exclude paths matching a pattern
pixi run zarrcade discover /path/to/zarrs -o images.csv --exclude "*.backup"

# Output as TSV
pixi run zarrcade discover /path/to/zarrs -o images.tsv --format tsv
```

**Output columns:** `path`, `name`, `group_path`, `uri` (if `--base-url`), and optionally `axes_order`, `dimensions`, `dimensions_voxels`, `voxel_sizes`, `chunk_size`, `num_channels`, `num_timepoints`, `dtype`, `compression`, `channel_colors`, `channel_names`.

### Generate MIPs and Thumbnails

Create Maximum Intensity Projections and thumbnails from zarr containers:

```bash
# Generate from a directory scan (default naming preserves the input path structure)
pixi run zarrcade mips /path/to/zarrs -o /output/thumbnails

# Generate from a CSV (reads zarr paths from the first column)
pixi run zarrcade mips --input-csv images.csv -o /output/thumbnails

# Write an updated CSV with thumbnail paths
pixi run zarrcade mips --input-csv images.csv -o /output/thumbnails \
    --output-csv images-with-thumbs.csv

# Skip already-generated thumbnails
pixi run zarrcade mips /path/to/zarrs -o /output/thumbnails --skip-existing

# Flat output: use zarr basename instead of preserving directories
pixi run zarrcade mips /path/to/zarrs -o /output/thumbnails --naming flat
```

**Naming strategies:** `nested` (default) preserves the input directory layout under the output dir; `flat` uses each zarr's basename (e.g. `sample_a_thumbnail.jpg`).

**Image processing options:** `--thumbnail-size`, `--mip-size`, `--clahe-limit`, `--p-lower`, `--p-upper`, `--max-gain`, `--target-max`, `--ignore-zeros`, `--k-bg`, `--min-dynamic`. Run `pixi run zarrcade mips --help` for full details.

### Resize Existing Thumbnails

If you already have rendered PNG/JPEG images (e.g. from another pipeline) and just want to shrink them to gallery-friendly sizes, use `thumbnails`:

```bash
# Resize every .png under a directory into a JPEG of the same name
pixi run zarrcade thumbnails /path/to/images --size 300 --quality 85

# Write outputs into a separate directory with a suffix
pixi run zarrcade thumbnails /path/to/images -o /path/to/out \
    --suffix _thumb --format jpg
```

Options: `--pattern` (glob, default `*.png`), `--size`, `--quality`, `--format` (`jpg`|`png`), `--suffix`, `--overwrite`.

### Embed Thumbnails into Zarr

Write existing thumbnail images into their zarr containers using the [thumbnails convention](https://github.com/clbarnes/zarr-convention-thumbnails). The SPA reads these directly from `zarr.json`, so a separate thumbnail column in the CSV is no longer needed:

```bash
# Read a CSV with zarr paths in column 1 and thumbnail paths in column 2
pixi run zarrcade embed --input-csv images-with-thumbs.csv

# Resolve relative paths against base URLs
pixi run zarrcade embed --input-csv images-with-thumbs.csv \
    --zarr-base-url https://bucket.s3.amazonaws.com/zarrs \
    --thumbnail-base-url https://example.com/thumbs

# Skip zarrs that already have thumbnails registered
pixi run zarrcade embed --input-csv images-with-thumbs.csv --skip-existing
```

For each row this writes the original thumbnail plus a downsampled, brightness-stretched JPEG under `<zarr>/thumbnails/` and registers both in the zarr root's attrs. Options: `--size`, `--jpeg-quality`, `--p-lower`, `--p-upper`.


## Web SPA Configuration

The SPA is configured via a `config.json` file. Here is a complete example:

```json
{
  "dataUrl": "https://example.com/images.csv",
  "title": "My Image Collection",
  "data": {
    "delimiter": ",",
    "pathColumn": "path",
    "baseUrl": "https://s3.example.com/zarrs",
    "thumbnailColumn": "thumbnail_url",
    "thumbnailBaseUrl": "https://s3.example.com/thumbnails"
  },
  "display": {
    "titleTemplate": "{name} - {date}",
    "hideColumns": ["path", "thumbnail_url"],
    "pageSize": 50
  },
  "filters": [
    { "column": "species", "label": "Species" },
    { "column": "probes", "label": "Probes", "dataType": "csv" }
  ],
  "viewers": [
    {
      "name": "Neuroglancer",
      "icon": "neuroglancer.png",
      "urlTemplate": "https://neuroglancer-demo.appspot.com/#!{URL}",
      "enabled": true
    }
  ],
  "branding": {
    "headerLeftLogo": "https://example.com/logo.png",
    "footerLinks": [
      { "label": "About", "url": "https://example.com/about" }
    ]
  }
}
```

### Configuration Reference

| Section | Field | Description | Default |
|---------|-------|-------------|---------|
| *(root)* | `dataUrl` | URL to CSV/TSV data file. Required for the gallery; if empty or missing the SPA renders a Welcome / getting-started screen. | -- |
| *(root)* | `title` | Page title | `"Zarrcade"` |
| `data` | `delimiter` | CSV delimiter: `","`, `"\t"`, or `"auto"` | `","` |
| `data` | `pathColumn` | Column containing zarr paths | `"path"` |
| `data` | `baseUrl` | Base URL prepended to relative paths | -- |
| `data` | `thumbnailColumn` | Column containing thumbnail paths | -- |
| `data` | `thumbnailBaseUrl` | Base URL prepended to thumbnail paths | -- |
| `display` | `titleTemplate` | Template with `{columnName}` variables | -- |
| `display` | `titleColumn` | Column to use as card title | -- |
| `display` | `hideColumns` | Columns to hide from card display | `[]` |
| `display` | `pageSize` | Results per page | `50` |
| `filters[]` | `column` | CSV column to filter on | -- |
| `filters[]` | `label` | Display label for the dropdown | -- |
| `filters[]` | `dataType` | `"string"` or `"csv"` (comma-separated values in cells) | `"string"` |
| `viewers[]` | `name` | Display name | -- |
| `viewers[]` | `icon` | Icon filename (in `/icons/` directory) | -- |
| `viewers[]` | `urlTemplate` | URL template. Placeholders: `{URL}` (raw zarr URL), `{ENCODED_URL}` (percent-encoded), `{NAME}` (zarr basename, no `.zarr`) | -- |
| `viewers[]` | `enabled` | Show/hide this viewer | -- |
| `branding` | `headerLeftLogo` | URL for left header logo | -- |
| `branding` | `headerRightLogo` | URL for right header logo | -- |
| `branding` | `footerLinks` | Array of `{label, url}` footer links | `[]` |

### URL Parameters

The SPA supports these URL parameters for deep linking:

| Parameter | Description |
|-----------|-------------|
| `?config=<url>` | Load configuration from a remote URL |
| `?data=<url>` | Override the `dataUrl` from config |
| `?search=<term>` | Pre-set search term |
| `?page=<number>` | Navigate to a specific page |
| `?detail=<index>` | Open the detail page for a specific image |
| `?<column>=<value>` | Pre-set a filter value (column name as key) |

### Built-in Viewers

Zarrcade ships with these viewers pre-configured. If you don't set `viewers` in your config, Neuroglancer and Avivator appear on every image card; the others are defined but turned off.

| Viewer | Shown by default? | Description |
|--------|-------------------|-------------|
| [Neuroglancer](https://github.com/google/neuroglancer) | Yes | 3D volumetric viewer by Google |
| [Avivator](https://github.com/hms-dbmi/viv) | Yes | OME-NGFF viewer by HMS-DBMI |
| [OME-NGFF Validator](https://ome.github.io/ome-ngff-validator/) | No | Validates OME-NGFF compliance |
| [Vol-E](https://volumeviewer.allencell.org/) | No | 3D Cell Viewer by Allen Institute |
| [BioNGFF](https://biongff.github.io/biongff-viewer/) | No | BioNGFF web viewer |

**Customizing the list.** Setting `viewers` in `config.json` *replaces* the built-in list — it is not merged. To enable Vol-E alongside the defaults, redeclare every viewer you want to keep:

```json
"viewers": [
  { "name": "Neuroglancer", "icon": "neuroglancer.png", "urlTemplate": "https://neuroglancer-demo.appspot.com/#!{URL}", "enabled": true },
  { "name": "Avivator",     "icon": "vizarr_logo.png",  "urlTemplate": "https://janeliascicomp.github.io/viv/?image_url={ENCODED_URL}", "enabled": true },
  { "name": "Vol-E",        "icon": "aics_website-3d-cell-viewer.png", "urlTemplate": "https://volumeviewer.allencell.org/viewer?url={ENCODED_URL}", "enabled": true }
]
```

You can also add your own entries — any viewer that accepts a zarr URL via query string works. See the [`viewers[]` rows](#configuration-reference) above for the `urlTemplate` placeholders (`{URL}`, `{ENCODED_URL}`, `{NAME}`).


## Deployment

The SPA is a pure static site. `npm run build` in `web/` produces a `dist/` directory of HTML/JS/CSS that can be served by any static host (S3, GitHub Pages, Netlify, a plain web server, etc.).

### Custom Configuration

The deployed `config.json` (next to `index.html`) is read at load time. You can also point the SPA at a different config:

```
https://your-host.example.com/?config=https://s3.example.com/my-config.json
```

Priority: `?config=<url>` query param > `./config.local.json` (dev only, gitignored) > `./config.json` > built-in defaults.

### Serving Data Files

The CSV data file and thumbnail images must be accessible via HTTP from the browser. Common approaches:

1. **Same server**: Place CSV and thumbnails in a web-accessible directory and use relative or absolute URLs in `config.json`
2. **S3/cloud storage**: Host on S3 (or similar) with public read access and use the HTTPS URL
3. **Separate web server**: Serve data files from another origin (CORS headers may be needed)


## Web Development

```bash
cd web
npm install
npm run dev       # Start dev server with hot reload
npm run build     # Production build to dist/
npm run preview   # Preview the production build
```

The dev server runs at [http://localhost:5173](http://localhost:5173). Place a `config.json` in `web/public/` pointing to your data, or use `?data=<url>` to load data directly.


## CSV Data Format

The SPA reads standard CSV or TSV files. Requirements:

* One row per image
* A **path column** (configurable, default: `path`) containing zarr container paths or full URIs
* Optional **thumbnail column** containing thumbnail image paths or URLs
* Any additional columns become searchable metadata displayed on image cards

Example CSV:
```csv
path,name,species,tissue,thumbnail_url
experiment1/sample_a.zarr,Sample A,Mouse,Brain,thumbnails/sample_a.jpg
experiment2/sample_b.zarr,Sample B,Human,Liver,thumbnails/sample_b.jpg
```

### Thumbnail Resolution

For each row the SPA tries these sources in order:

1. The configured `thumbnailColumn` from the CSV row (resolved against `thumbnailBaseUrl` if relative).
2. Thumbnails registered in the zarr itself via the [thumbnails convention](https://github.com/clbarnes/zarr-convention-thumbnails) — read lazily from `<zarr>/zarr.json` `attributes.thumbnails` as cards scroll into view. Write these with `zarrcade embed`.
3. A built-in placeholder (`./icons/zarr.jpg`).


## Project Structure

```
zarrcade/                       # repo root
├── pixi.toml                  # Pixi environment and CLI dependencies
├── zarrcade/                   # Python CLI source code
│   ├── __main__.py            # CLI entry point (Click)
│   ├── commands/
│   │   ├── discover.py         # zarrcade discover command
│   │   ├── generate_mips.py    # zarrcade mips command
│   │   ├── thumbnails.py       # zarrcade thumbnails command
│   │   └── embed_thumbnails.py # zarrcade embed command
│   └── core/
│       ├── agent.py           # Image discovery protocol
│       ├── filestore.py       # Storage abstraction (local + S3 via fsspec)
│       ├── model.py           # Data models (Image, Channel)
│       ├── omezarr.py         # OME-Zarr discovery agent
│       ├── thumbnails.py      # MIP generation (microfilm + CLAHE)
│       └── zarr_thumbnails.py # Thumbnails convention read/write helpers
│
├── web/                        # React + TypeScript SPA
│   ├── package.json
│   ├── vite.config.ts
│   ├── public/
│   │   ├── config.json        # Default configuration
│   │   └── icons/             # Viewer icons and fallback image
│   └── src/
│       ├── App.tsx            # Main application component (gallery + detail routing)
│       ├── config.ts          # Configuration loader
│       ├── types.ts           # TypeScript type definitions
│       ├── components/        # TopBar, SearchBar, FilterDropdowns, Gallery,
│       │                      # ImageCard, ImageDetail, Pagination, ThemeToggle,
│       │                      # Welcome, Footer
│       ├── hooks/             # useData, useSearch, useFilters, usePagination,
│       │                      # useTheme, useIntersectionObserver, useZarrThumbnail
│       ├── utils/             # csv, viewers, clipboard, zarrThumbnails
│       └── styles/            # CSS (Pico CSS framework)
│
└── examples/                   # Example datasets and configurations
    ├── flyefish.csv
    ├── openorganelle.tsv
    ├── t3.csv
    ├── config-flyefish.json
    ├── config-openorganelle.json
    └── config-t3.json
```


## Known Limitations

* The OME-Zarr discovery agent does not support the full OME-Zarr specification and may fail with certain image layouts. If you encounter an error, please [open an issue](https://github.com/JaneliaSciComp/zarrcade/issues).
* The SPA loads the entire CSV into the browser, so very large datasets (100k+ rows) may impact performance.
* Search is substring-based across all columns; there is no field-specific or boolean query syntax.


## License

[BSD 3-Clause License](LICENSE) - Howard Hughes Medical Institute


## Attributions

* <https://www.iconsdb.com/black-icons/copy-link-icon.html>
* <https://www.veryicon.com/icons/education-technology/smart-campus-1/view-details-2.html>
