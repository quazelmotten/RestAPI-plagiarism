import React from 'react';
import {
  Input,
  Select,
  Text,
  VStack,
  SimpleGrid,
} from '@chakra-ui/react';
import type { Filters } from '../types';

interface SubmissionsFiltersProps {
  filters: Filters;
  onFilterChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  uniqueLanguages: string[];
  uniqueTaskIds: string[];
  allStatuses: string[];
}

export const SubmissionsFilters: React.FC<SubmissionsFiltersProps> = ({
  filters,
  onFilterChange,
  uniqueLanguages,
  uniqueTaskIds,
  allStatuses,
}) => {
  return (
    <VStack spacing={4} align="stretch" p={4}>
      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
        <div>
          <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
            File Name
          </Text>
          <Input
            name="filename"
            size="sm"
            value={filters.filename}
            onChange={onFilterChange}
            placeholder="Search..."
          />
        </div>

        <div>
          <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
            Language
          </Text>
          <Select
            name="language"
            size="sm"
            value={filters.language}
            onChange={onFilterChange}
          >
            <option value="">All</option>
            {uniqueLanguages.map(lang => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </Select>
        </div>

        <div>
          <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
            Status
          </Text>
          <Select
            name="status"
            size="sm"
            value={filters.status}
            onChange={onFilterChange}
          >
            <option value="">All</option>
            {allStatuses.map(status => (
              <option key={status} value={status}>{status}</option>
            ))}
          </Select>
        </div>

        <div>
          <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
            Similarity (e.g. &gt;50% or 0.5)
          </Text>
          <Input
            name="similarity"
            size="sm"
            value={filters.similarity}
            onChange={onFilterChange}
            placeholder=">50%, <0.3, etc."
          />
        </div>

        <div>
          <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
            Submitted Date
          </Text>
          <Input
            name="submittedAt"
            type="date"
            size="sm"
            value={filters.submittedAt}
            onChange={onFilterChange}
          />
        </div>

        <div>
          <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
            Task ID
          </Text>
          <Select
            name="task_id"
            size="sm"
            value={filters.task_id}
            onChange={onFilterChange}
          >
            <option value="">All</option>
            {uniqueTaskIds.map(id => (
              <option key={id} value={id}>{id}</option>
            ))}
          </Select>
        </div>
      </SimpleGrid>
    </VStack>
  );
};

export default SubmissionsFilters;
