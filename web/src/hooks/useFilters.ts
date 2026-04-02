/**
 * Hook for dropdown filter management
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import type { ImageRow, FilterConfig, FilterState } from '../types';

interface UseFiltersResult {
  activeFilters: FilterState;
  setFilter: (column: string, value: string) => void;
  clearFilters: () => void;
  filteredData: ImageRow[];
  filterOptions: Record<string, string[]>;
}

export function useFilters(
  data: ImageRow[],
  filterConfigs: FilterConfig[]
): UseFiltersResult {
  const [activeFilters, setActiveFilters] = useState<FilterState>({});

  // Initialize filters from URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial: FilterState = {};

    filterConfigs.forEach((config) => {
      const value = params.get(config.column);
      if (value) {
        initial[config.column] = value;
      }
    });

    if (Object.keys(initial).length > 0) {
      setActiveFilters(initial);
    }
  }, [filterConfigs]);

  // Compute unique values for each filter column
  const filterOptions = useMemo(() => {
    const options: Record<string, Set<string>> = {};

    filterConfigs.forEach((config) => {
      options[config.column] = new Set<string>();
    });

    const hasEmpty: Record<string, boolean> = {};

    data.forEach((row) => {
      filterConfigs.forEach((config) => {
        const value = row[config.column];
        if (value === undefined || value === null || value === '') {
          hasEmpty[config.column] = true;
        } else if (config.dataType === 'csv' && typeof value === 'string') {
          // Split CSV values
          value.split(',').forEach((v) => {
            const trimmed = v.trim();
            if (trimmed) {
              options[config.column].add(trimmed);
            }
          });
        } else {
          options[config.column].add(String(value));
        }
      });
    });

    // Convert sets to sorted arrays, with "None" first if there are empty rows
    const result: Record<string, string[]> = {};
    Object.entries(options).forEach(([column, valueSet]) => {
      const sorted = Array.from(valueSet).sort();
      if (hasEmpty[column]) {
        sorted.unshift('None');
      }
      result[column] = sorted;
    });

    return result;
  }, [data, filterConfigs]);

  // Update URL when filters change
  const updateUrl = useCallback((newFilters: FilterState) => {
    const params = new URLSearchParams(window.location.search);

    // Remove old filter params
    filterConfigs.forEach((config) => {
      params.delete(config.column);
    });

    // Add new filter params
    Object.entries(newFilters).forEach(([key, value]) => {
      if (value) {
        params.set(key, value);
      }
    });

    const newUrl = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
    window.history.replaceState({}, '', newUrl);
  }, [filterConfigs]);

  const setFilter = useCallback((column: string, value: string) => {
    setActiveFilters((prev) => {
      const newFilters = { ...prev };
      if (value) {
        newFilters[column] = value;
      } else {
        delete newFilters[column];
      }
      updateUrl(newFilters);
      return newFilters;
    });
  }, [updateUrl]);

  const clearFilters = useCallback(() => {
    setActiveFilters({});
    updateUrl({});
  }, [updateUrl]);

  // Apply filters to data
  const filteredData = useMemo(() => {
    if (Object.keys(activeFilters).length === 0) {
      return data;
    }

    return data.filter((row) => {
      return Object.entries(activeFilters).every(([column, filterValue]) => {
        const cellValue = row[column];
        if (cellValue === undefined || cellValue === null || cellValue === '') {
          return filterValue === 'None';
        }
        if (filterValue === 'None') {
          return false;
        }

        const config = filterConfigs.find((c) => c.column === column);
        if (config?.dataType === 'csv' && typeof cellValue === 'string') {
          // Check if any CSV value matches
          const values = cellValue.split(',').map((v) => v.trim());
          return values.includes(filterValue);
        }

        return String(cellValue).toLowerCase().includes(filterValue.toLowerCase());
      });
    });
  }, [data, activeFilters, filterConfigs]);

  return {
    activeFilters,
    setFilter,
    clearFilters,
    filteredData,
    filterOptions,
  };
}
