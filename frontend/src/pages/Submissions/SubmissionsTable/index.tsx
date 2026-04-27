import React, { useMemo, useState } from 'react';
import {
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Button,
  HStack,
  Text,
  Box,
  Flex,
  Icon,
} from '@chakra-ui/react';
import { FiArrowRight, FiChevronUp, FiChevronDown, FiInbox } from 'react-icons/fi';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
} from '@tanstack/react-table';
import type { ColumnDef, ColumnSort, SortingState } from '@tanstack/react-table';
import type { FileSubmission } from '../types';
import { formatDate, formatSimilarity, getStatusColor } from '../utils/formatters';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

interface SubmissionsTableProps {
  data: FileSubmission[];
  isLoading?: boolean;
}

export const SubmissionsTable: React.FC<SubmissionsTableProps> = ({
  data,
  isLoading = false,
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation(['submissions', 'status', 'common']);
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<FileSubmission>[]>(
    () => [
      {
        accessorKey: 'filename',
        header: t('table.fileName'),
        size: 250,
      },
      {
        accessorKey: 'language',
        header: t('table.language'),
        size: 120,
        cell: (info) => (
          <Badge colorScheme="blue" variant="outline">
            {info.getValue<string>()}
          </Badge>
        ),
      },
      {
        accessorKey: 'status',
        header: t('table.status'),
        size: 120,
        cell: (info) => {
          const status = info.getValue<string>();
          return (
            <Badge colorScheme={getStatusColor(status)}>
              {t(`status:${status}`)}
            </Badge>
          );
        },
      },
      {
        accessorKey: 'similarity',
        header: t('table.similarity'),
        size: 100,
        cell: (info) => {
          const similarity = info.getValue<number | null>();
          return formatSimilarity(similarity);
        },
      },
      {
        accessorKey: 'created_at',
        header: t('table.submittedAt'),
        size: 150,
        cell: (info) => {
          const date = info.getValue<string>();
          return formatDate(date);
        },
      },
      {
        accessorKey: 'task_id',
        header: t('table.taskId'),
        size: 150,
      },
       {
         accessorKey: 'assignment_name',
         header: t('table.assignment'),
         size: 180,
         cell: (info) => {
           const name = info.getValue<string | null>();
           return name ? <Text fontWeight="medium">{name}</Text> : <Text color="gray.400">—</Text>;
         },
       },
       {
         accessorKey: 'subject_name',
         header: t('table.subject'),
         size: 150,
         cell: (info) => {
           const name = info.getValue<string | null>();
           return name ? <Text fontWeight="medium">{name}</Text> : <Text color="gray.400">—</Text>;
         },
       },
      {
        id: 'actions',
        header: t('table.actions'),
        size: 100,
        cell: (info) => {
          const row = info.row.original;
          return (
            <Button
              size="sm"
              leftIcon={<FiArrowRight />}
              variant="ghost"
              onClick={() => navigate(`/dashboard/results?filter=${row.id}`)}
            >
              {t('table.goToTask')}
            </Button>
          );
        },
        enableSorting: false,
      },
    ],
    [navigate, t]
  );

  const table = useReactTable<FileSubmission>({
    data,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const handleSort = (columnId: string) => {
    const column = table.getColumn(columnId);
    if (!column) return;

    const currentSort = column.getIsSorted();
    // Toggle: unsorted -> desc -> asc -> desc -> asc...
    const newDesc = currentSort !== 'desc';
    const newSorting: ColumnSort[] = [{ id: columnId, desc: newDesc }];
    setSorting(newSorting);
  };

  const renderSortIcon = (columnId: string) => {
    const column = table.getColumn(columnId);
    if (!column || !column.getIsSorted()) {
      return null;
    }
    return column.getIsSorted() === 'asc' ? (
      <FiChevronUp />
    ) : (
      <FiChevronDown />
    );
  };

  if (isLoading) {
    return (
      <Box textAlign="center" py={8}>
        <Text>{t('loading')}</Text>
      </Box>
    );
  }

  if (data.length === 0) {
    return (
      <Flex direction="column" align="center" justify="center" py={16} color="gray.500">
        <Icon as={FiInbox} boxSize={16} mb={4} opacity={0.5} />
        <Text fontWeight="medium" fontSize="lg">{t('noMatches')}</Text>
        <Text fontSize="sm">{t('common:labels.noSubmissionsFound')}</Text>
      </Flex>
    );
  }

  return (
    <Box overflowX="auto" overflowY="auto" w="100%" h="100%">
      <Table variant="simple" size="sm" layout="fixed" w="100%">
        <Thead position="sticky" top={0} zIndex={1} bg="gray.50" _dark={{ bg: 'gray.700' }}>
          {table.getHeaderGroups().map(headerGroup => (
            <Tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <Th
                  key={header.id}
                  onClick={() => {
                    if (header.column.getCanSort()) {
                      handleSort(header.column.id);
                    }
                  }}
                  cursor={header.column.getCanSort() ? 'pointer' : undefined}
                  userSelect="none"
                  _hover={header.column.getCanSort() ? { bg: 'gray.100', _dark: { bg: 'gray.600' } } : undefined}
                >
                  <HStack spacing={1} justify="space-between">
                    <Text as="span">{flexRender(header.column.columnDef.header, header.getContext())}</Text>
                    {renderSortIcon(header.column.id)}
                  </HStack>
                </Th>
              ))}
            </Tr>
          ))}
        </Thead>
        <Tbody _dark={{ bg: 'gray.800' }}>
          {table.getRowModel().rows.map(row => (
            <Tr key={row.original.id}>
              {row.getVisibleCells().map(cell => (
                <Td key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </Td>
              ))}
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
};

export default SubmissionsTable;
