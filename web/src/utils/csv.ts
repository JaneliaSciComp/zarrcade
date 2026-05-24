/**
 * CSV data utilities
 */

import type { ImageRow, AppConfig } from '../types';
import { sanitizeTitle, stripTags } from './sanitize';

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

export const THUMBNAIL_PLACEHOLDER = './icons/zarr.jpg';

/**
 * Resolve a CSV-provided thumbnail URL, or return null if the row has none.
 */
export function getCsvThumbnailUrl(row: ImageRow, config: AppConfig): string | null {
  const thumbnailColumn = config.data?.thumbnailColumn;
  if (!thumbnailColumn) return null;

  const thumbnail = row[thumbnailColumn];
  if (!thumbnail) return null;

  const thumbStr = String(thumbnail);
  if (thumbStr.startsWith('http://') || thumbStr.startsWith('https://')) {
    return thumbStr;
  }

  const thumbBase = config.data?.thumbnailBaseUrl;
  if (thumbBase) {
    return `${thumbBase.replace(/\/$/, '')}/${thumbStr.replace(/^\//, '')}`;
  }

  if (config.dataUrl) {
    return resolveRelativeUrl(thumbStr, config.dataUrl);
  }

  return thumbStr;
}

/**
 * Resolve a CSV-provided full-size image URL, or return null if the row has none.
 * Mirrors getCsvThumbnailUrl but uses fullSizeColumn / fullSizeBaseUrl.
 */
export function getFullSizeImageUrl(row: ImageRow, config: AppConfig): string | null {
  const fullSizeColumn = config.data?.fullSizeColumn;
  if (!fullSizeColumn) return null;

  const value = row[fullSizeColumn];
  if (!value) return null;

  const str = String(value);
  if (str.startsWith('http://') || str.startsWith('https://')) {
    return str;
  }

  const base = config.data?.fullSizeBaseUrl;
  if (base) {
    return `${base.replace(/\/$/, '')}/${str.replace(/^\//, '')}`;
  }

  if (config.dataUrl) {
    return resolveRelativeUrl(str, config.dataUrl);
  }

  return str;
}

/**
 * Get the display title for an image row.
 *
 * The result is rendered into the DOM via dangerouslySetInnerHTML, so it
 * MUST be sanitized before reaching this function's callers. Both the
 * author-supplied template AND CSV cell substitutions are routed through
 * the same DOMPurify pass — neither can be trusted: configs can be loaded
 * via ?config=<url>, and CSV cells can contain whatever an upstream
 * pipeline produced.
 */
export function getTitle(row: ImageRow, config: AppConfig): string {
  const template = config.display?.titleTemplate;
  const titleColumn = config.display?.titleColumn;

  let raw: string;
  if (template) {
    raw = template.replace(/\{([^}]+)\}/g, (_, key) => {
      const value = row[key];
      return value !== undefined ? String(value) : '';
    });
  } else if (titleColumn && row[titleColumn] !== undefined) {
    raw = String(row[titleColumn]);
  } else {
    const pathColumn = config.data?.pathColumn || 'path';
    const path = row[pathColumn];
    raw = path ? String(path) : 'Untitled';
  }

  return sanitizeTitle(raw);
}

/**
 * Plain-text version of the title for use in `alt` attributes,
 * `document.title`, copy/paste, and screen readers — anywhere markup
 * would be noisy or wrong. Same trust posture as getTitle: the source
 * string is untrusted, so the output is run through DOMPurify with
 * everything stripped.
 */
export function getPlainTitle(row: ImageRow, config: AppConfig): string {
  return stripTags(getTitle(row, config));
}

/**
 * Get visible columns (excluding hidden ones)
 */
export function getVisibleColumns(columns: string[], config: AppConfig): string[] {
  const hideColumns = config.display?.hideColumns || [];
  return columns.filter((col) => !hideColumns.includes(col));
}

/**
 * Generate a CSV string from data rows and trigger a download.
 *
 * Exports every column — `hideColumns` only governs what the gallery and
 * detail page show; the downloaded file is for offline analysis, so
 * stripping internal columns (paths, thumbnail filenames, etc.) would
 * make the export less useful, not more.
 */
export function downloadCsv(data: ImageRow[], columns: string[], _config: AppConfig, filename: string): void {
  const escape = (val: string) => {
    if (val.includes(',') || val.includes('"') || val.includes('\n')) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  };

  const header = columns.map(escape).join(',');
  const rows = data.map((row) =>
    columns.map((col) => escape(String(row[col] ?? ''))).join(',')
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
