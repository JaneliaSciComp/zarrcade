# @janelia/zarrcade

Static web gallery for browsing, searching, and visualizing collections of [OME-NGFF (OME-Zarr)](https://github.com/ome/ngff) images.

[![CI](https://github.com/JaneliaSciComp/zarrcade/actions/workflows/ci.yml/badge.svg)](https://github.com/JaneliaSciComp/zarrcade/actions/workflows/ci.yml)

This package ships a prebuilt single-page app plus a small `zarrcade` CLI that scaffolds a deployable site directory. There is no backend, no database, and no React/Vite toolchain on your side — you edit a JSON config, point it at a CSV manifest of zarrs, and drop the directory onto any static host.

## Quick start

```bash
npx @janelia/zarrcade init my-gallery
cd my-gallery
# Open config.json and set "dataUrl" to your CSV/TSV of zarrs.
# Optionally tweak title, filters, viewers, branding.
npx serve .                # preview locally
```

When you're happy with it, upload the directory to any static host: S3, GitHub Pages, nginx, Netlify, Cloudflare Pages, etc.

The CLI also accepts `--version` and `--help`.

## What's in the scaffolded directory

```
my-gallery/
├── index.html         # the SPA entry point
├── config.json        # your site's configuration (edit this)
├── assets/            # hashed JS/CSS/font bundles
└── icons/             # viewer icons and the zarr fallback thumbnail
```

`config.json` is the only file you typically need to edit. The minimum required field is `dataUrl` — a URL (relative or absolute) to a CSV or TSV manifest listing your zarr containers.

## CSV format

One row per image. Required: a `path` column (configurable via `data.pathColumn`) containing zarr URLs or paths. Optional: a thumbnail column and any number of metadata columns that become searchable / filterable in the gallery.

```csv
path,name,species,tissue,thumbnail_url
experiment1/sample_a.zarr,Sample A,Mouse,Brain,thumbnails/sample_a.jpg
experiment2/sample_b.zarr,Sample B,Human,Liver,thumbnails/sample_b.jpg
```

You can generate this manifest yourself, or use the companion Python CLI ([repo root](https://github.com/JaneliaSciComp/zarrcade)) which walks local or S3-backed zarr trees and emits the CSV for you, optionally with thumbnails.

## Configuration

See the full [Configuration Reference](https://github.com/JaneliaSciComp/zarrcade#web-spa-configuration) in the project README — it covers `data`, `display`, `filters`, `viewers`, `branding`, URL parameters, and the built-in viewer list.

## License

[BSD 3-Clause](https://github.com/JaneliaSciComp/zarrcade/blob/main/LICENSE) — Howard Hughes Medical Institute.
