/**
 * Hook for text search across all columns
 */

import { useState, useMemo, useCallback } from 'react';
import type { ImageRow } from '../types';

interface UseSearchResult {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  searchResults: ImageRow[];
}

export function useSearch(data: ImageRow[]): UseSearchResult {
  const [searchTerm, setSearchTerm] = useState('');

  // Initialize from URL
  useState(() => {
    const params = new URLSearchParams(window.location.search);
    const term = params.get('search');
    if (term) {
      setSearchTerm(term);
    }
  });

  // Update URL when search changes
  const updateSearchTerm = useCallback((term: string) => {
    setSearchTerm(term);

    // Update URL
    const params = new URLSearchParams(window.location.search);
    if (term) {
      params.set('search', term);
    } else {
      params.delete('search');
    }
    const newUrl = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
    window.history.replaceState({}, '', newUrl);
  }, []);

  const searchResults = useMemo(() => {
    if (!searchTerm.trim()) {
      return data;
    }

    const lowerTerm = searchTerm.toLowerCase();

    return data.filter((row) => {
      // Search across all string values in the row
      return Object.values(row).some((value) => {
        if (typeof value === 'string') {
          return value.toLowerCase().includes(lowerTerm);
        }
        if (typeof value === 'number') {
          return value.toString().includes(lowerTerm);
        }
        return false;
      });
    });
  }, [data, searchTerm]);

  return {
    searchTerm,
    setSearchTerm: updateSearchTerm,
    searchResults,
  };
}
