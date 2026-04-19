/**
 * Lazy-fetch a thumbnail registered on a zarr via the thumbnails convention.
 * Only runs when `enabled` is true (used with viewport observation on cards).
 */

import { useEffect, useState } from 'react';
import { fetchBestThumbnail, type SelectedThumbnail } from '../utils/zarrThumbnails';

export function useZarrThumbnail(
  zarrUrl: string | null,
  targetSize: number,
  enabled: boolean
): SelectedThumbnail | null {
  const [thumb, setThumb] = useState<SelectedThumbnail | null>(null);

  useEffect(() => {
    setThumb(null);
    if (!enabled || !zarrUrl) return;
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
