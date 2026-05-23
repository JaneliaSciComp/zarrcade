/**
 * Hook for loading and parsing CSV data
 */

import { useState, useEffect } from 'react';
import Papa from 'papaparse';
import type { AppConfig, ImageRow } from '../types';

interface UseDataResult {
  data: ImageRow[];
  columns: string[];
  loading: boolean;
  error: Error | null;
}

export function useData(config: AppConfig | null): UseDataResult {
  const [data, setData] = useState<ImageRow[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!config?.dataUrl) {
      setLoading(false);
      return;
    }

    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(config.dataUrl);
        if (!response.ok) {
          // statusText is often empty over HTTP/2, so include the status code.
          const reason = response.statusText
            ? `${response.status} ${response.statusText}`
            : String(response.status);
          throw new Error(`Failed to fetch ${config.dataUrl}: ${reason}`);
        }

        const text = await response.text();

        // Reject obvious non-CSV bodies (HTML/XML error pages, JSON responses,
        // dev-server SPA fallbacks). Without this, PapaParse will happily parse
        // them into garbage rows and the gallery silently shows blank results.
        const head = text.trimStart().slice(0, 1);
        if (head === '<' || head === '{' || head === '[') {
          throw new Error(
            `Response from ${config.dataUrl} is not CSV (got ${head === '<' ? 'HTML/XML' : 'JSON'})`,
          );
        }

        // Parse CSV/TSV
        const delimiter = config.data?.delimiter || ',';
        const result = Papa.parse<Record<string, string>>(text, {
          header: true,
          delimiter: delimiter === 'auto' ? undefined : delimiter,
          skipEmptyLines: true,
          transformHeader: (header) => header.trim(),
        });

        if (result.errors.length > 0) {
          console.warn('CSV parse warnings:', result.errors);
        }

        const fields = result.meta.fields || [];
        const rows = result.data as ImageRow[];
        const pathColumn = config.data?.pathColumn || 'path';
        const hasPathValues = rows.some((r) => {
          const v = r[pathColumn];
          return v !== undefined && v !== null && String(v).trim() !== '';
        });
        if (fields.length === 0 || rows.length === 0 || !hasPathValues) {
          throw new Error(
            `No rows found in ${config.dataUrl} (expected a CSV with a "${pathColumn}" column)`,
          );
        }

        setColumns(fields);
        setData(rows);
      } catch (e) {
        setError(e instanceof Error ? e : new Error('Unknown error'));
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [config?.dataUrl, config?.data?.delimiter]);

  return { data, columns, loading, error };
}
