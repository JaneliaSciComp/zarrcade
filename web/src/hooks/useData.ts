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
          throw new Error(`Failed to fetch data: ${response.statusText}`);
        }

        const text = await response.text();

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

        // Store columns and data
        setColumns(result.meta.fields || []);
        setData(result.data as ImageRow[]);
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
