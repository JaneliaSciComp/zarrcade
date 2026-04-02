/**
 * CSV data utilities
 */

import type { ImageRow, AppConfig } from '../types';

/**
 * Get the path/URI for an image row
 */
export function getImagePath(row: ImageRow, config: AppConfig): string {
  const pathColumn = config.data?.pathColumn || 'path';
  const path = row[pathColumn];

  if (!path) {
    return '';
  }

  const pathStr = String(path);

  // If already a full URL, return as-is
  if (pathStr.startsWith('http://') || pathStr.startsWith('https://') || pathStr.startsWith('s3://')) {
    return pathStr;
  }

  // Otherwise, prepend base URL if configured
  const baseUrl = config.data?.baseUrl;
  if (baseUrl) {
    return `${baseUrl.replace(/\/$/, '')}/${pathStr.replace(/^\//, '')}`;
  }

  return pathStr;
}

/**
 * Get the thumbnail URL for an image row
 */
export function getThumbnailUrl(row: ImageRow, config: AppConfig): string {
  const thumbnailColumn = config.data?.thumbnailColumn;

  // If thumbnail column is configured and has a value, use it
  if (thumbnailColumn) {
    const thumbnail = row[thumbnailColumn];
    if (thumbnail) {
      const thumbStr = String(thumbnail);
      // If already a full URL, return as-is
      if (thumbStr.startsWith('http://') || thumbStr.startsWith('https://')) {
        return thumbStr;
      }
      // Otherwise, prepend thumbnail base URL if configured
      const thumbBase = config.data?.thumbnailBaseUrl;
      if (thumbBase) {
        return `${thumbBase.replace(/\/$/, '')}/${thumbStr.replace(/^\//, '')}`;
      }
      return thumbStr;
    }
  }

  // Fallback to default placeholder
  return './icons/zarr.jpg';
}

/**
 * Get the display title for an image row
 */
export function getTitle(row: ImageRow, config: AppConfig): string {
  const template = config.display?.titleTemplate;
  const titleColumn = config.display?.titleColumn;

  // If template is configured, use it
  if (template) {
    return template.replace(/\{([^}]+)\}/g, (_, key) => {
      const value = row[key];
      return value !== undefined ? String(value) : '';
    });
  }

  // If title column is configured, use it
  if (titleColumn) {
    const value = row[titleColumn];
    if (value !== undefined) {
      return String(value);
    }
  }

  // Fallback to path
  const pathColumn = config.data?.pathColumn || 'path';
  const path = row[pathColumn];
  return path ? String(path) : 'Untitled';
}

/**
 * Get visible columns (excluding hidden ones)
 */
export function getVisibleColumns(columns: string[], config: AppConfig): string[] {
  const hideColumns = config.display?.hideColumns || [];
  return columns.filter((col) => !hideColumns.includes(col));
}
