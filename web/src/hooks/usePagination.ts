/**
 * Hook for client-side pagination
 */

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import type { ImageRow } from '../types';

interface UsePaginationResult {
  currentPage: number;
  pageSize: number;
  totalPages: number;
  totalItems: number;
  paginatedData: ImageRow[];
  goToPage: (page: number) => void;
  setPageSize: (size: number) => void;
  startIndex: number;
  endIndex: number;
}

function readPageFromUrl(): number {
  const params = new URLSearchParams(window.location.search);
  const page = params.get('page');
  if (page) {
    const pageNum = parseInt(page, 10);
    if (!isNaN(pageNum) && pageNum > 0) {
      return pageNum;
    }
  }
  return 1;
}

export function usePagination(
  data: ImageRow[],
  initialPageSize: number = 50
): UsePaginationResult {
  const [currentPage, setCurrentPage] = useState(readPageFromUrl);
  const [pageSize, setPageSizeState] = useState(initialPageSize);

  // Reset to page 1 when the user changes a filter/search (which changes
  // the result set length), but NOT during the initial CSV load (0 → N),
  // which would otherwise clobber a `?page=` deep link on refresh. We arm
  // the reset only after we've seen non-zero data for the first time.
  const prevLengthRef = useRef<number | null>(null);
  useEffect(() => {
    if (prevLengthRef.current === null) {
      if (data.length > 0) {
        prevLengthRef.current = data.length;
      }
      return;
    }
    if (prevLengthRef.current !== data.length) {
      prevLengthRef.current = data.length;
      setCurrentPage(1);
    }
  }, [data.length]);

  // Restore page on browser back/forward.
  useEffect(() => {
    const onPop = () => setCurrentPage(readPageFromUrl());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(data.length / pageSize));
  }, [data.length, pageSize]);

  // Ensure current page is valid. Skip while data is still loading (length
  // 0 forces totalPages to 1, which would otherwise clobber a `?page=N>1`
  // deep link on refresh before the CSV arrives).
  useEffect(() => {
    if (data.length === 0) return;
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages, data.length]);

  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return data.slice(start, end);
  }, [data, currentPage, pageSize]);

  const startIndex = (currentPage - 1) * pageSize + 1;
  const endIndex = Math.min(currentPage * pageSize, data.length);

  // Update URL when page changes
  const updateUrl = useCallback((page: number) => {
    const params = new URLSearchParams(window.location.search);
    if (page > 1) {
      params.set('page', page.toString());
    } else {
      params.delete('page');
    }
    const newUrl = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
    window.history.replaceState({}, '', newUrl);
  }, []);

  const goToPage = useCallback((page: number) => {
    const validPage = Math.max(1, Math.min(page, totalPages));
    setCurrentPage(validPage);
    updateUrl(validPage);
  }, [totalPages, updateUrl]);

  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setCurrentPage(1);
    updateUrl(1);
  }, [updateUrl]);

  return {
    currentPage,
    pageSize,
    totalPages,
    totalItems: data.length,
    paginatedData,
    goToPage,
    setPageSize,
    startIndex,
    endIndex,
  };
}
