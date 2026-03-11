import React from 'react';
import {
  HStack,
  Button,
  Text,
  Select,
  Input,
  InputGroup,
  InputRightElement,
} from '@chakra-ui/react';
import { FiChevronLeft, FiChevronRight } from 'react-icons/fi';
import type { PaginationInfo } from '../types';

interface PaginationControlsProps {
  pagination: PaginationInfo;
  onPageChange: (newOffset: number) => void;
  onPageSizeChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
}

export const PaginationControls: React.FC<PaginationControlsProps> = ({
  pagination,
  onPageChange,
  onPageSizeChange,
}) => {
  const { offset, limit, total, totalPages, showingStart, showingEnd } = pagination;

  const currentPage = totalPages > 0 ? Math.floor(offset / limit) + 1 : 0;

  const handleGoToPage = () => {
    const input = document.getElementById('goto-page') as HTMLInputElement;
    const pageNum = parseInt(input.value, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      const newOffset = (pageNum - 1) * limit;
      onPageChange(newOffset);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleGoToPage();
    }
  };

  return (
    <HStack
      justify="space-between"
      align="center"
      wrap="wrap"
      spacing={4}
      p={4}
      borderBottomWidth={1}
      borderColor="gray.200"
      _dark={{ borderColor: 'gray.700' }}
    >
      <HStack spacing={2}>
        <Button
          size="sm"
          onClick={() => onPageChange(offset - limit)}
          isDisabled={offset === 0}
          leftIcon={<FiChevronLeft />}
        >
          Previous
        </Button>
        <Button
          size="sm"
          onClick={() => onPageChange(offset + limit)}
          isDisabled={offset + limit >= total}
          rightIcon={<FiChevronRight />}
        >
          Next
        </Button>
      </HStack>

      <HStack spacing={2}>
        <Text fontSize="sm" color="gray.600" _dark={{ color: 'gray.400' }}>
          Page Size:
        </Text>
        <Select
          value={limit.toString()}
          onChange={onPageSizeChange}
          w="80px"
          size="sm"
        >
          <option value="25">25</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </Select>
      </HStack>

      <Text fontSize="sm" color="gray.500" _dark={{ color: 'gray.400' }}>
        Showing {showingStart} - {showingEnd} of {total} files
      </Text>

      <HStack spacing={2}>
        <Text fontSize="sm" color="gray.600" _dark={{ color: 'gray.400' }}>
          Go to page:
        </Text>
        <InputGroup size="sm" w="80px">
          <Input
            id="goto-page"
            type="number"
            min={1}
            max={totalPages}
            defaultValue={currentPage}
            onKeyDown={handleKeyPress}
          />
          <InputRightElement width="2.5rem">
            <Button
              size="xs"
              h="1.75rem"
              onClick={handleGoToPage}
              isDisabled={totalPages <= 1 || currentPage === 0}
            >
              Go
            </Button>
          </InputRightElement>
        </InputGroup>
      </HStack>
    </HStack>
  );
};

export default PaginationControls;
