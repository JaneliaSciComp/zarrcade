/**
 * Read thumbnails registered on a zarr via the thumbnails convention:
 * https://github.com/clbarnes/zarr-convention-thumbnails
 *
 * Only `zarr.json` (v3) is consulted.
 */

interface ThumbnailEntry {
  width: number;
  height: number;
  media_type: string;
  description?: string;
  path?: string;
  url?: string;
}

export interface SelectedThumbnail {
  url: string;
  width: number;
  height: number;
}

const cache = new Map<string, Promise<SelectedThumbnail | null>>();

function longestEdge(t: { width: number; height: number }): number {
  return Math.max(t.width, t.height);
}

/**
 * Pick the entry closest to the target. Prefer one slightly larger
 * (so it never needs to be upsampled when displayed); if none are
 * at least target size, pick the largest available.
 */
function selectBest(entries: ThumbnailEntry[], target: number): ThumbnailEntry | null {
  if (!entries.length) return null;
  const withEdge = entries.map((e) => ({ e, edge: longestEdge(e) }));

  const geq = withEdge.filter((x) => x.edge >= target).sort((a, b) => a.edge - b.edge);
  if (geq.length > 0) return geq[0].e;

  const sorted = [...withEdge].sort((a, b) => b.edge - a.edge);
  return sorted[0].e;
}

function resolveEntryUrl(entry: ThumbnailEntry, zarrUrl: string): string | null {
  if (entry.url) return entry.url;
  if (entry.path) return zarrUrl.replace(/\/$/, '') + '/' + entry.path.replace(/^\//, '');
  return null;
}

export function fetchBestThumbnail(
  zarrUrl: string,
  targetSize: number
): Promise<SelectedThumbnail | null> {
  const key = `${zarrUrl}::${targetSize}`;
  const hit = cache.get(key);
  if (hit) return hit;

  const metadataUrl = zarrUrl.replace(/\/$/, '') + '/zarr.json';

  const promise: Promise<SelectedThumbnail | null> = (async () => {
    let res: Response;
    try {
      res = await fetch(metadataUrl);
    } catch (err) {
      console.error(`[zarr-thumbnails] network error fetching ${metadataUrl}:`, err);
      return null;
    }

    if (res.status === 404) return null;
    if (!res.ok) {
      console.error(`[zarr-thumbnails] ${metadataUrl} responded ${res.status} ${res.statusText}`);
      return null;
    }

    let meta: unknown;
    try {
      meta = await res.json();
    } catch (err) {
      console.error(`[zarr-thumbnails] invalid JSON at ${metadataUrl}:`, err);
      return null;
    }

    const attrs = (meta as { attributes?: { thumbnails?: unknown } })?.attributes;
    const entries = attrs?.thumbnails;
    if (!Array.isArray(entries) || entries.length === 0) return null;

    const best = selectBest(entries as ThumbnailEntry[], targetSize);
    if (!best) return null;

    const url = resolveEntryUrl(best, zarrUrl);
    if (!url) return null;
    return { url, width: best.width, height: best.height };
  })();

  cache.set(key, promise);
  return promise;
}
