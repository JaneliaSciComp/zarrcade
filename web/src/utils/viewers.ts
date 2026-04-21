/**
 * Viewer URL generation utilities
 */

import type { Viewer } from '../types';

/**
 * Generate a viewer URL by substituting the data URL into the template
 */
function extractName(url: string): string {
  const path = url.replace(/\/+$/, '');
  const basename = path.split('/').pop() || 'image';
  return basename.replace(/\.zarr$/i, '');
}

export function getViewerUrl(viewer: Viewer, dataUrl: string): string {
  const name = extractName(dataUrl);
  return viewer.urlTemplate
    .split('{ENCODED_URL}').join(encodeURIComponent(dataUrl))
    .split('{URL}').join(dataUrl)
    .split('{NAME}').join(name);
}

/**
 * Get enabled viewers from config
 */
export function getEnabledViewers(viewers: Viewer[] | undefined): Viewer[] {
  if (!viewers) return [];
  return viewers.filter((v) => v.enabled);
}
