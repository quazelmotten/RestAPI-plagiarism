import React from 'react';
import {
  Card,
  CardBody,
  Box,
  VStack,
  Text,
  Spinner,
  useColorModeValue,
} from '@chakra-ui/react';
import ReviewQueueItem from './ReviewQueueItem';
import type { PlagiarismResult } from '../../types';

interface ReviewListProps {
  items: PlagiarismResult[];
  isLoading: boolean;
  isEmpty: boolean;
  isEmptyMessage?: string;
  selectedIndex: number;
  onSelectItem: (item: PlagiarismResult, index: number) => void;
  onAction: (item: PlagiarismResult) => void;
}

export const ReviewList: React.FC<ReviewListProps> = ({
  items,
  isLoading,
  isEmpty,
  isEmptyMessage = 'No pairs found',
  selectedIndex,
  onSelectItem,
  onAction,
}) => {
  const mutedTextColor = useColorModeValue("gray.500", "gray.400");
  const defaultBorderColor = useColorModeValue('gray.200', 'gray.600');
  const hoverBorderColor = useColorModeValue('brand.300', 'brand.400');

  if (isLoading) {
    return (
      <Card flex="1" display="flex" flexDirection="column" minH={0}>
        <CardBody display="flex" alignItems="center" justifyContent="center" flex={1}>
          <Spinner size="lg" />
        </CardBody>
      </Card>
    );
  }

  if (isEmpty) {
    return (
      <Card flex="1" display="flex" flexDirection="column" minH={0}>
        <CardBody display="flex" alignItems="center" justifyContent="center" flex={1}>
          <Text color={mutedTextColor}>{isEmptyMessage}</Text>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card flex="1" display="flex" flexDirection="column" minH={0}>
      <Box flex="1" overflowY="auto" minH={0}>
        <VStack align="stretch" spacing={2} p={2}>
          {items.map((item, idx) => (
            <Box
              key={item.id || `${item.file_a?.id}-${item.file_b?.id}`}
              borderWidth={selectedIndex === idx ? '2px' : '1px'}
              borderColor={selectedIndex === idx ? 'brand.500' : defaultBorderColor}
              borderRadius="md"
              transition="border-color 0.15s"
              cursor="pointer"
              _hover={{ borderColor: hoverBorderColor }}
              onClick={() => onSelectItem(item, idx)}
            >
              <ReviewQueueItem
                item={item}
                index={idx}
                onReview={(pair) => onSelectItem(pair, idx)}
                onAction={() => onAction(item)}
              />
            </Box>
          ))}
        </VStack>
      </Box>
    </Card>
  );
};