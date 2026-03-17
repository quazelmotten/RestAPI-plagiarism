import React from 'react';
import { Card, CardBody, Heading, VStack, Box, HStack, Text, Progress } from '@chakra-ui/react';

interface SimilarityDistributionProps {
  totalPairs: number;
  stats: {
    high: number;
    medium: number;
    low: number;
  };
  cardBg?: string;
}

const SimilarityDistribution: React.FC<SimilarityDistributionProps> = ({ totalPairs, stats, cardBg }) => {
  return (
    <Card bg={cardBg}>
      <CardBody>
        <Heading size="sm" mb={4}>Similarity Distribution</Heading>
        <VStack align="stretch" spacing={3}>
          <Box>
            <HStack justify="space-between" mb={1}>
              <Text fontSize="sm">High (≥80%)</Text>
              <Text fontSize="sm" fontWeight="bold" color="red.500">{stats.high}</Text>
            </HStack>
            <Progress
              value={stats.high}
              max={totalPairs || 1}
              colorScheme="red"
              borderRadius="full"
            />
          </Box>
          <Box>
            <HStack justify="space-between" mb={1}>
              <Text fontSize="sm">Medium (50-79%)</Text>
              <Text fontSize="sm" fontWeight="bold" color="orange.500">{stats.medium}</Text>
            </HStack>
            <Progress
              value={stats.medium}
              max={totalPairs || 1}
              colorScheme="orange"
              borderRadius="full"
            />
          </Box>
          <Box>
            <HStack justify="space-between" mb={1}>
              <Text fontSize="sm">Low (&lt;50%)</Text>
              <Text fontSize="sm" fontWeight="bold" color="green.500">{stats.low}</Text>
            </HStack>
            <Progress
              value={stats.low}
              max={totalPairs || 1}
              colorScheme="green"
              borderRadius="full"
            />
          </Box>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default SimilarityDistribution;
