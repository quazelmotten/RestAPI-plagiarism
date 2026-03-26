import React, { useMemo } from 'react';
import { Card, CardBody, HStack, Text, Badge, VStack, Box, useColorModeValue } from '@chakra-ui/react';
import type { PlagiarismResult } from '../../types';

interface ResultsListProps {
  results: PlagiarismResult[];
  totalPairs: number;
  borderColor: string;
  hoverBg: string;
  getSimilarityColor: (similarity: number) => string;
  handleCompare: (result: PlagiarismResult) => void;
  loadingMoreResults?: boolean;
  onLoadMore?: () => void;
  cardBg?: string;
}

const ResultsList: React.FC<ResultsListProps> = ({
  results,
  totalPairs,
  borderColor,
  hoverBg,
  getSimilarityColor,
  handleCompare,
  cardBg,
}) => {
  const listNoticeBg = useColorModeValue('gray.50', 'gray.700');
  const listNoticeColor = useColorModeValue('gray.600', 'gray.400');
  // Cap at 50 results for Top Similarities view
  const displayResults = useMemo(() => results.slice(0, 50), [results]);
  const showingCount = displayResults.length;

  return (
    <Card bg={cardBg}>
      <CardBody>
        <HStack justify="space-between" align="center" mb={4}>
          <Text fontSize="md" fontWeight="bold">Top Similarities</Text>
          <HStack>
            <Text color="gray.500" fontSize="sm">
              Showing {showingCount} of {totalPairs} pairs
            </Text>
          </HStack>
        </HStack>

        <VStack align="stretch" spacing={2}>
          {displayResults.map((result, idx) => (
              <HStack
                key={idx}
                p={3}
                borderWidth={1}
                borderColor={borderColor}
                borderRadius="md"
                cursor="pointer"
                _hover={{ bg: hoverBg }}
                onClick={() => handleCompare(result)}
                justify="space-between"
                align="center"
              >
                <HStack flex={1} spacing={2} align="center">
                  <VStack align="start" spacing={0}>
                    <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="200px">
                      {result.file_a.filename}
                    </Text>
                    {result.file_a.task_id && (
                      <Text fontSize="xs" color="gray.500" noOfLines={1} maxW="120px">
                        ({result.file_a.task_id.substring(0, 8)}...)
                      </Text>
                    )}
                  </VStack>
                  <Text fontSize="sm" color="gray.500" fontWeight="medium">vs</Text>
                  <VStack align="start" spacing={0}>
                    <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="200px">
                      {result.file_b.filename}
                    </Text>
                    {result.file_b.task_id && (
                      <Text fontSize="xs" color="gray.500" noOfLines={1} maxW="120px">
                        ({result.file_b.task_id.substring(0, 8)}...)
                      </Text>
                    )}
                  </VStack>
                </HStack>
                <Badge
                  colorScheme={getSimilarityColor(result.ast_similarity || 0)}
                  fontSize="md"
                  px={3}
                  py={1}
                  ml={4}
                >
                  {((result.ast_similarity || 0) * 100).toFixed(1)}%
                </Badge>
              </HStack>
            ))}
        </VStack>

        {totalPairs > 50 && (
          <Box textAlign="center" mt={4} py={2} px={4} bg={listNoticeBg} borderRadius="md">
            <Text fontSize="sm" color={listNoticeColor}>
              Full list contains {totalPairs} pairs. Explore histogram for distribution analysis.
            </Text>
          </Box>
        )}
      </CardBody>
    </Card>
  );
};

export default ResultsList;
