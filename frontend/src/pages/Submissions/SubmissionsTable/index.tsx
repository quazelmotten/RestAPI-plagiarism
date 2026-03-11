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
} from '@chakra-ui/react';
import { FiArrowRight, FiChevronUp, FiChevronDown } from 'react-icons/fi';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
} from '@tanstack/react-table';
import type { ColumnDef, ColumnSort, SortingState, CellContext } from '@tanstack/react-table';
import type { FileSubmission } from '../types';
import { formatDate, formatSimilarity, getStatusColor } from '../utils/formatters';
import { useNavigate } from 'react-router';

interface SubmissionsTableProps {
  data: FileSubmission[];
  isLoading?: boolean;
}

export const SubmissionsTable: React.FC<SubmissionsTableProps> = ({
  data,
  isLoading = false,
}) => {
  const navigate = useNavigate();
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<FileSubmission>[]>(
    () => [
      {
        accessorKey: 'filename',
        header: 'File Name',
        size: 250,
      },
      {
        accessorKey: 'language',
        header: 'Language',
        size: 120,
        cell: (info) => (
          <Badge colorScheme="blue" variant="outline">
            {info.getValue<string>()}
          </Badge>
        ),
      },
      {
        accessorKey: 'status',
        header: 'Status',
        size: 120,
        cell: (info) => {
          const status = info.getValue<string>();
          return (
            <Badge colorScheme={getStatusColor(status)}>
              {status}
            </Badge>
          );
        },
      },
      {
        accessorKey: 'similarity',
        header: 'Similarity',
        size: 100,
        cell: (info) => {
          const similarity = info.getValue<number | null>();
          return formatSimilarity(similarity);
        },
      },
      {
        accessorKey: 'created_at',
        header: 'Submitted At',
        size: 150,
        cell: (info) => {
          const date = info.getValue<string>();
          return formatDate(date);
        },
      },
      {
        accessorKey: 'task_id',
        header: 'Task ID',
        size: 150,
      },
      {
        id: 'actions',
        header: 'Actions',
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
              Go to Task
            </Button>
          );
        },
        enableSorting: false,
      },
    ],
    [navigate]
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
        <Text>Loading...</Text>
      </Box>
    );
  }

  if (data.length === 0) {
    return (
      <Box textAlign="center" py={8}>
        <Text color="gray.500">No submissions match the current filters</Text>
      </Box>
    );
  }

  return (
    <Box overflowX="auto" w="100%">
      <Table variant="simple" size="sm" layout="fixed" w="100%">
        <Thead position="sticky" top={0} bg="white" _dark={{ bg: 'gray.800' }}>
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
                  _hover={header.column.getCanSort() ? { bg: 'gray.100', _dark: { bg: 'gray.700' } } : undefined}
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
        <Tbody>
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
