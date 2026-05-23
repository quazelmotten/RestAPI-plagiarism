import React from 'react';
import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  useColorModeValue,
  Icon,
} from '@chakra-ui/react';
import { FiAlertTriangle, FiCheckCircle, FiMinus, FiBarChart2, FiInbox } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import SimilarityDistribution from '../../../components/Results/SimilarityDistribution';
import { getSimilarityColor } from '../../../utils/statusColors';
import type { PlagiarismResult } from '../../../types';

interface AssignmentStatsTabProps {
  results: PlagiarismResult[];
  totalPairs: number;
  stats: {
    high: number;
    medium: number;
    low: number;
    avg: number;
  };
  assignmentId?: string;
  taskId?: string;
}

const AssignmentStatsTab: React.FC<AssignmentStatsTabProps> = ({
  results,
  totalPairs,
  stats,
  assignmentId,
  taskId,
}) => {
  const { t } = useTranslation(['assignments', 'common', 'results']);
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  if (totalPairs === 0) {
    return (
      <Flex flex={1} align="center" justify="center" direction="column" color="gray.500" py={12}>
        <Icon as={FiInbox} boxSize={10} mb={3} />
        <Text fontWeight="medium">{t('results:noResultsYet')}</Text>
        <Text fontSize="sm" mt={1} color="gray.400">{t('results:uploadFilesToSeeStats')}</Text>
      </Flex>
    );
  }

  return (
    <VStack align="stretch" spacing={4} flex={1} overflow="auto">
      {/* Summary Cards */}
      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
        <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4}>
          <Stat>
            <StatLabel>{t('common:labels.totalPairs')}</StatLabel>
            <StatNumber>{totalPairs}</StatNumber>
            <StatHelpText>{t('common:labels.comparedPairs')}</StatHelpText>
          </Stat>
        </Box>

        <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4}>
          <Stat>
            <StatLabel>{t('common:labels.avgSimilarity')}</StatLabel>
            <StatNumber color={getSimilarityColor(stats.avg)}>{(stats.avg * 100).toFixed(1)}%</StatNumber>
            <StatHelpText>{t('common:labels.acrossAllPairs')}</StatHelpText>
          </Stat>
        </Box>

        <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4}>
          <Stat>
            <StatLabel>
              <HStack spacing={1}>
                <Icon as={FiAlertTriangle} color="red.500" />
                <Text>{t('common:labels.highSimilarity')}</Text>
              </HStack>
            </StatLabel>
            <StatNumber color="red.500">{stats.high}</StatNumber>
            <StatHelpText>{t('common:labels.requiresReview')}</StatHelpText>
          </Stat>
        </Box>

        <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4}>
          <Stat>
            <StatLabel>
              <HStack spacing={1}>
                <Icon as={FiCheckCircle} color="green.500" />
                <Text>{t('common:labels.lowSimilarity')}</Text>
              </HStack>
            </StatLabel>
            <StatNumber color="green.500">{stats.low}</StatNumber>
            <StatHelpText>{t('common:labels.likelyOriginal')}</StatHelpText>
          </Stat>
        </Box>
      </SimpleGrid>

      {/* Distribution Chart */}
      <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4}>
        <VStack align="stretch" spacing={4}>
          <HStack>
            <Icon as={FiBarChart2} boxSize={5} color="brand.500" />
            <Text fontSize="lg" fontWeight="semibold">{t('results:distribution.title')}</Text>
          </HStack>
          <SimilarityDistribution
            results={results}
            totalPairs={totalPairs}
            cardBg={cardBg}
            assignmentId={assignmentId}
            taskId={taskId}
            stats={stats}
          />
        </VStack>
      </Box>
    </VStack>
  );
};

export default AssignmentStatsTab;
