import React from 'react';
import {
  Card,
  CardBody,
  HStack,
  Text,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  IconButton,
} from '@chakra-ui/react';
import { FiFilter, FiSearch, FiChevronLeft, FiChevronRight } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';

interface ReviewToolbarProps {
  searchFilter: string;
  setSearchFilter: (value: string) => void;
  similarityFilter: string;
  setSimilarityFilter: (value: string) => void;
  pageSize: number;
  setPageSize: (value: number) => void;
  showingStart: number;
  showingEnd: number;
  total: number;
  page: number;
  totalPages: number;
  onPrevPage: () => void;
  onNextPage: () => void;
  isFirstPage: boolean;
  isLastPage: boolean;
}

export const ReviewToolbar: React.FC<ReviewToolbarProps> = ({
  searchFilter,
  setSearchFilter,
  similarityFilter,
  setSimilarityFilter,
  pageSize,
  setPageSize,
  showingStart,
  showingEnd,
  total,
  page,
  totalPages,
  onPrevPage,
  onNextPage,
  isFirstPage,
  isLastPage,
}) => {
  const { t } = useTranslation(['common', 'review']);

  return (
    <Card>
      <CardBody py={2}>
        <HStack spacing={4} flexWrap="wrap">
          <HStack spacing={2}>
            <FiFilter />
            <Text fontSize="sm" fontWeight="medium">{t('review:filters')}</Text>
          </HStack>
          
          <InputGroup size="sm" w="180px">
            <InputLeftElement>
              <FiSearch />
            </InputLeftElement>
            <Input
              placeholder={t('common:placeholders.searchFiles')}
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
            />
          </InputGroup>
          
          <Input
            size="sm"
            w="120px"
            placeholder={t('common:placeholders.similarityFilter')}
            value={similarityFilter}
            onChange={(e) => setSimilarityFilter(e.target.value)}
          />
          
          <Select
            size="sm"
            w="80px"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </Select>

          <IconButton
            aria-label={t('common:aria.previousPage')}
            icon={<FiChevronLeft />}
            size="sm"
            onClick={onPrevPage}
            isDisabled={isFirstPage}
          />
          <Text fontSize="sm">
            {page + 1} / {totalPages}
          </Text>
          <IconButton
            aria-label={t('common:aria.nextPage')}
            icon={<FiChevronRight />}
            size="sm"
            onClick={onNextPage}
            isDisabled={isLastPage}
          />
          
          <Text fontSize="sm" color="gray.500">
            {t('pagination.showing', { start: showingStart, end: showingEnd, total })}
          </Text>
        </HStack>
      </CardBody>
    </Card>
  );
};