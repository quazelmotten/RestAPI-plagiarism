import React from 'react';
import {
  Input,
  Select,
  Text,
  VStack,
  SimpleGrid,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import type { Filters } from '../types';

interface SubmissionsFiltersProps {
  filters: Filters;
  onFilterChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  uniqueLanguages: string[];
  uniqueTaskIds: string[];
  uniqueAssignments: Array<{ id: string; name: string }>;
  uniqueSubjects: Array<{ id: string; name: string }>;
  allStatuses: string[];
}

export const SubmissionsFilters: React.FC<SubmissionsFiltersProps> = ({
  filters,
  onFilterChange,
  uniqueLanguages,
  uniqueTaskIds,
  uniqueAssignments,
  uniqueSubjects,
  allStatuses,
}) => {
  const { t } = useTranslation(['submissions', 'common', 'status']);

  return (
    <VStack spacing={4} align="stretch" p={4}>
       <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
         {/* existing filters */}
          <div>
            <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
              {t('filters.fileName')}
            </Text>
            <Input
              name="filename"
              size="sm"
              value={filters.filename}
              onChange={onFilterChange}
              placeholder={t('common:search')}
            />
          </div>

          <div>
            <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
              {t('filters.language')}
            </Text>
            <Select
              name="language"
              size="sm"
              value={filters.language}
              onChange={onFilterChange}
            >
              <option value="">{t('common:all')}</option>
              {uniqueLanguages.map(lang => (
                <option key={lang} value={lang}>{lang}</option>
              ))}
            </Select>
          </div>

          <div>
            <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
              {t('filters.status')}
            </Text>
            <Select
              name="status"
              size="sm"
              value={filters.status}
              onChange={onFilterChange}
            >
              <option value="">{t('common:all')}</option>
              {allStatuses.map(status => (
                <option key={status} value={status}>{t(`status:${status}`)}</option>
              ))}
            </Select>
          </div>

          <div>
            <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
              {t('filters.similarity')}
            </Text>
            <Input
              name="similarity"
              size="sm"
              value={filters.similarity}
              onChange={onFilterChange}
              placeholder={t('filters.similarityPlaceholder')}
            />
          </div>

          <div>
            <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
              {t('filters.submittedDate')}
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
              {t('filters.taskId')}
            </Text>
            <Select
              name="task_id"
              size="sm"
              value={filters.task_id}
              onChange={onFilterChange}
            >
              <option value="">{t('common:all')}</option>
              {uniqueTaskIds.map(id => (
                <option key={id} value={id}>{id}</option>
              ))}
            </Select>
          </div>

          <div>
            <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
              Assignment
            </Text>
            <Select
              name="assignment_id"
              size="sm"
              value={filters.assignment_id}
              onChange={onFilterChange}
              maxW="150px"
            >
              <option value="">All</option>
              {uniqueAssignments.map(assignment => (
                <option key={assignment.id} value={assignment.id}>{assignment.name}</option>
              ))}
            </Select>
          </div>

          <div>
            <Text fontSize="xs" fontWeight="medium" mb={1} color="gray.600" _dark={{ color: 'gray.400' }}>
              Subject
            </Text>
            <Select
              name="subject_id"
              size="sm"
              value={filters.subject_id}
              onChange={onFilterChange}
              maxW="150px"
            >
              <option value="">All</option>
              {uniqueSubjects.map(subject => (
                <option key={subject.id} value={subject.id}>{subject.name}</option>
              ))}
            </Select>
          </div>
        </SimpleGrid>
      </VStack>
    );
  };

export default SubmissionsFilters;
