import { useState, useMemo, useCallback } from 'react';

/**
 * Pagination hook
 *
 * Args:
 * - total: Total number of items (required)
 * - pageSize: Items per page (default 50)
 * - initialPage: Starting page (default 0)
 */

export function usePagination({ total, pageSize = 50, initialPage = 0 }: { total: number; pageSize?: number; initialPage?: number }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const [page, setPage] = useState(Math.min(initialPage, totalPages - 1));

  /**
   * Navigate to next page
   */
  const nextPage = useCallback(() => {
    setPage(prev => Math.min(prev + 1, totalPages - 1));
  }, [totalPages]);

  /**
   * Navigate to previous page
   */
  const prevPage = useCallback(() => {
    setPage(prev => Math.max(prev - 1, 0));
  }, []);

  /**
   * Go to specific page
   *
   * Args:
   * - pageNum: Page number (0-indexed)
   */
  const goToPage = useCallback((pageNum: number) => {
    setPage(Math.min(Math.max(pageNum, 0), totalPages - 1));
  }, [totalPages]);

  /**
   * Paginated data info
   *
   * Returns: {
   *   start: Index of first item in current page
   *   end: Index of last item in current page + 1
   *   totalPages: Total number of pages
   * }
   */
  const paginatedInfo = useMemo(() => {
    return {
      start: page * pageSize,
      end: Math.min((page + 1) * pageSize, total)
    };
  }, [page, pageSize, total]);

  return {
    page,
    totalPages,
    nextPage,
    prevPage,
    goToPage,
    isFirstPage: page === 0,
    isLastPage: page >= totalPages - 1,
    start: paginatedInfo.start,
    end: paginatedInfo.end
  };
}