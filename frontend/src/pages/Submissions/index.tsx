import React, { useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardBody,
  Spinner,
  Alert,
  AlertIcon,
  Button,
  Flex,
  Icon,
  Text,
} from '@chakra-ui/react';
import { FiInbox } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useSubmissions } from './hooks/useSubmissions';
import { useSubmissionsMetadata } from './hooks/useSubmissionsMetadata';
import { PaginationControls } from './PaginationControls';
import { SubmissionsFilters } from './SubmissionsFilters';
import { SubmissionsTable } from './SubmissionsTable';
import type { Filters, PaginationInfo } from './types';
import { ALL_STATUSES } from './utils/formatters';

const SubmissionsContent: React.FC = () => {
  const { t } = useTranslation(['submissions', 'common']);
  const [filters, setFilters] = useState<Filters>({
    filename: '',
    language: '',
    status: '',
    similarity: '',
    submittedAt: '',
    task_id: '',
    assignment_id: '',
    subject_id: '',
  });
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(50);

  const { data: metadata } = useSubmissionsMetadata();
  const uniqueAssignments = metadata?.assignments ?? [];
  const uniqueSubjects = metadata?.subjects ?? [];
  const { data: submissionsData, isLoading, error, refetch } = useSubmissions({
    offset,
    limit: pageSize,
    filters,
  });

  const total = submissionsData?.total ?? 0;
  const files = submissionsData?.items ?? [];

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const showingStart = total > 0 ? offset + 1 : 0;
  const showingEnd = Math.min(offset + pageSize, total);

  const paginationInfo: PaginationInfo = {
    offset,
    limit: pageSize,
    total,
    totalPages,
    showingStart,
    showingEnd,
  };

  const handleFilterChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const { name, value } = e.target;
      setFilters(prev => ({ ...prev, [name]: value }));
      // Reset to page 0 when filter changes
      setOffset(0);
    },
    []
  );

  const handlePageChange = useCallback((newOffset: number) => {
    const clamped = Math.max(0, newOffset);
    setOffset(clamped);
  }, []);

  const handlePageSizeChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newSize = parseInt(e.target.value, 10);
      setPageSize(newSize);
      setOffset(0);
    },
    []
  );

  if (error) {
    return (
      <Alert status="error">
        <AlertIcon />
        {error instanceof Error ? error.message : t('common:error')}
        <Button ml={4} onClick={() => refetch()}>
          {t('common:retry')}
        </Button>
      </Alert>
    );
  }

  return (
    <Card flex="1" display="flex" flexDirection="column" minH="0" overflow="hidden" w="100%">
      <CardBody flex="1" display="flex" flexDirection="column" p={0} minH="0" overflow="hidden">
        {/* Filters */}
        <SubmissionsFilters
          filters={filters}
          onFilterChange={handleFilterChange}
          uniqueLanguages={metadata?.languages ?? []}
          uniqueTaskIds={metadata?.taskIds ?? []}
          uniqueAssignments={uniqueAssignments}
          uniqueSubjects={uniqueSubjects}
          allStatuses={ALL_STATUSES}
        />

        {/* Pagination at top */}
        <PaginationControls
          pagination={paginationInfo}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
        />

        {/* Table */}
        <Box flex="1" overflowY="auto" w="100%" minH="0">
          {isLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" h="400px">
              <Spinner size="xl" color="blue.500" />
            </Box>
          ) : (
            <SubmissionsTable data={files} isLoading={isLoading} />
          )}
        </Box>
      </CardBody>
    </Card>
  );
};

const SubmissionsPage: React.FC = () => {
  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
      <SubmissionsContent />
    </Box>
  );
};

export default SubmissionsPage;
