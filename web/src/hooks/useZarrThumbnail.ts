/**
 * Lazy-fetch a thumbnail registered on a zarr via the thumbnails convention.
 * Only runs when `enabled` is true (used with viewport observation on cards).
 */

import { useEffect, useState } from 'react';
import { fetchBestThumbnail, type SelectedThumbnail } from '../utils/zarrThumbnails';

/**
 * Returns:
 *   `undefined` — we haven't finished checking yet (initial state or in flight)
 *   `null`      — checked, no thumbnail is registered on the zarr
 *   value       — found a thumbnail
 * Callers can use this to distinguish "still loading" from "no thumbnail
 * exists" — important if the UI wants to show a skeleton vs. a fallback.
 */
export function useZarrThumbnail(
  zarrUrl: string | null,
  targetSize: number,
  enabled: boolean
): SelectedThumbnail | null | undefined {
  const [thumb, setThumb] = useState<SelectedThumbnail | null | undefined>(undefined);

  useEffect(() => {
    if (!enabled || !zarrUrl) {
      // No zarr URL → nothing to fetch and never will be. Resolve to "no
      // thumbnail" so callers don't sit on the loading state forever.
      setThumb(zarrUrl ? undefined : null);
      return;
    }
    setThumb(undefined);
    let cancelled = false;
    fetchBestThumbnail(zarrUrl, targetSize).then((result) => {
      if (!cancelled) setThumb(result);
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, zarrUrl, targetSize]);

  return thumb;
}
