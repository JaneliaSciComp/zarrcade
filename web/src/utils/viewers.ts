/**
 * Viewer URL generation utilities
 */

import type { Viewer } from '../types';

/**
 * Generate a viewer URL by substituting the data URL into the template
 */
export function getViewerUrl(viewer: Viewer, dataUrl: string): string {
  // URL encode the data URL for safety
  const encodedUrl = encodeURIComponent(dataUrl);
  return viewer.urlTemplate.replace('{URL}', encodedUrl);
}

/**
 * Get enabled viewers from config
 */
export function getEnabledViewers(viewers: Viewer[] | undefined): Viewer[] {
  if (!viewers) return [];
  return viewers.filter((v) => v.enabled);
}
