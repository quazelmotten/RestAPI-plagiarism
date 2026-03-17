import React from 'react';
import { Card, CardBody, HStack, Text, Badge, VStack, Box, Button } from '@chakra-ui/react';
import type { PlagiarismResult } from '../../types';

interface ResultsListProps {
  results: PlagiarismResult[];
  totalPairs: number;
  borderColor: string;
  hoverBg: string;
  getSimilarityColor: (similarity: number) => string;
  handleCompare: (result: PlagiarismResult) => void;
  loadingMoreResults: boolean;
  onLoadMore: () => void;
  cardBg?: string;
}

const ResultsList: React.FC<ResultsListProps> = ({
  results,
  totalPairs,
  borderColor,
  hoverBg,
  getSimilarityColor,
  handleCompare,
  loadingMoreResults,
  onLoadMore,
  cardBg,
}) => {
  return (
    <Card bg={cardBg}>
      <CardBody>
        <HStack justify="space-between" align="center" mb={4}>
          <Text fontSize="md" fontWeight="bold">Top Similarities</Text>
          <HStack>
            <Text color="gray.500" fontSize="sm">
              {results.length} pairs analyzed
            </Text>
          </HStack>
        </HStack>

        <VStack align="stretch" spacing={2}>
          {results
            .sort((a, b) => (b.ast_similarity || 0) - (a.ast_similarity || 0))
            .map((result, idx) => (
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
              >
                <HStack flex={1} spacing={4}>
                  <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="200px">
                    {result.file_a.filename}
                  </Text>
                  <Text fontSize="xs" color="gray.500">vs</Text>
                  <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="200px">
                    {result.file_b.filename}
                  </Text>
                </HStack>
                <Badge
                  colorScheme={getSimilarityColor(result.ast_similarity || 0)}
                  fontSize="md"
                  px={3}
                  py={1}
                >
                  {((result.ast_similarity || 0) * 100).toFixed(1)}%
                </Badge>
              </HStack>
            ))}
        </VStack>

        {results.length < totalPairs && (
          <Box textAlign="center" mt={4}>
            <Button
              onClick={onLoadMore}
              isLoading={loadingMoreResults}
              loadingText="Loading..."
            >
              Load More Results
            </Button>
          </Box>
        )}
      </CardBody>
    </Card>
  );
};

export default ResultsList;
