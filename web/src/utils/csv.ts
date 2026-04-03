/**
 * CSV data utilities
 */

import type { ImageRow, AppConfig } from '../types';

/**
 * Resolve a relative path against a base file URL.
 * Uses the browser's URL constructor for correct resolution.
 */
function resolveRelativeUrl(relativePath: string, baseFileUrl: string): string {
  const absoluteBase = new URL(baseFileUrl, window.location.href).href;
  return new URL(relativePath, absoluteBase).href;
}

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

  // Prepend base URL if configured
  const baseUrl = config.data?.baseUrl;
  if (baseUrl) {
    return `${baseUrl.replace(/\/$/, '')}/${pathStr.replace(/^\//, '')}`;
  }

  // Resolve relative to the CSV data URL
  if (config.dataUrl) {
    return resolveRelativeUrl(pathStr, config.dataUrl);
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
      // Prepend thumbnail base URL if configured
      const thumbBase = config.data?.thumbnailBaseUrl;
      if (thumbBase) {
        return `${thumbBase.replace(/\/$/, '')}/${thumbStr.replace(/^\//, '')}`;
      }
      // Resolve relative to the CSV data URL
      if (config.dataUrl) {
        return resolveRelativeUrl(thumbStr, config.dataUrl);
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

/**
 * Generate a CSV string from data rows and trigger a download
 */
export function downloadCsv(data: ImageRow[], columns: string[], config: AppConfig, filename: string): void {
  const visibleColumns = getVisibleColumns(columns, config);
  const escape = (val: string) => {
    if (val.includes(',') || val.includes('"') || val.includes('\n')) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  };

  const header = visibleColumns.map(escape).join(',');
  const rows = data.map((row) =>
    visibleColumns.map((col) => escape(String(row[col] ?? ''))).join(',')
  );
  const csv = [header, ...rows].join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Build a BioFile Finder URL for the current data
 */
export function getBioFileFinderUrl(config: AppConfig): string {
  const absoluteUrl = new URL(config.dataUrl, window.location.href).href;
  const title = config.title || 'zarrcade';
  const source = JSON.stringify({ name: `${title}-data`, type: 'csv', uri: absoluteUrl });

  // Build column widths: title column at 0.5, then first 3 filter columns
  const titleCol = config.display?.titleColumn || 'File Name';
  const filterCols = (config.filters || []).slice(0, 3).map((f) => f.column);
  const columnWidths = [titleCol + ':0.5', ...filterCols].join(',');

  const params = new URLSearchParams();
  params.set('c', columnWidths);
  params.set('v', '3');
  params.set('source', source);

  return `https://bff.allencell.org/app?${params.toString()}`;
}
