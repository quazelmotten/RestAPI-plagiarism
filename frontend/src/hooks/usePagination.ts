import { useState, useMemo, useCallback } from 'react';

export function usePagination({ total, pageSize = 50 }: { total: number; pageSize?: number; initialPage?: number }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const [page, setPage] = useState(0);

  const nextPage = useCallback(() => {
    setPage(prev => Math.min(prev + 1, totalPages - 1));
  }, [totalPages]);

  const prevPage = useCallback(() => {
    setPage(prev => Math.max(prev - 1, 0));
  }, []);

  const goToPage = useCallback((pageNum: number) => {
    setPage(Math.min(Math.max(pageNum, 0), totalPages - 1));
  }, [totalPages]);

  const safePage = Math.min(page, Math.max(0, totalPages - 1));

  const paginatedInfo = useMemo(() => ({
    start: safePage * pageSize,
    end: Math.min((safePage + 1) * pageSize, total),
  }), [safePage, pageSize, total]);

  return {
    page: safePage,
    totalPages,
    nextPage,
    prevPage,
    goToPage,
    isFirstPage: safePage === 0,
    isLastPage: safePage >= totalPages - 1,
    start: paginatedInfo.start,
    end: paginatedInfo.end,
  };
}
