import React from 'react';
import { Card, CardBody, Stat, StatLabel, StatNumber, Badge, HStack, SimpleGrid } from '@chakra-ui/react';
import type { TaskDetails } from '../../types';

interface TaskStatsProps {
  selectedTask: TaskDetails;
  avgSimilarity: number;
  getSimilarityColor: (similarity: number) => string;
  getStatusIcon: (status: string) => React.ReactNode;
  cardBg?: string;
}

const TaskStats: React.FC<TaskStatsProps> = ({ selectedTask, avgSimilarity, getSimilarityColor, getStatusIcon, cardBg }) => {
  const getStatusColorScheme = (status: string) => {
    return status === 'completed' ? 'green' : status === 'processing' ? 'orange' : 'yellow';
  };

  return (
    <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
      <Card bg={cardBg}>
        <CardBody>
          <Stat>
            <StatLabel>Files</StatLabel>
            <StatNumber>{selectedTask.files.length}</StatNumber>
          </Stat>
        </CardBody>
      </Card>

      <Card bg={cardBg}>
        <CardBody>
          <Stat>
            <StatLabel>Comparisons</StatLabel>
            <StatNumber>{selectedTask.total_pairs}</StatNumber>
          </Stat>
        </CardBody>
      </Card>

      <Card bg={cardBg}>
        <CardBody>
          <Stat>
            <StatLabel>Status</StatLabel>
            <HStack mt={2}>
              {getStatusIcon(selectedTask.status)}
              <Badge colorScheme={getStatusColorScheme(selectedTask.status)}>
                {selectedTask.status}
              </Badge>
            </HStack>
          </Stat>
        </CardBody>
      </Card>

      <Card bg={cardBg}>
        <CardBody>
          <Stat>
            <StatLabel>Avg Similarity</StatLabel>
            <StatNumber color={getSimilarityColor(avgSimilarity)}>
              {(avgSimilarity * 100).toFixed(1)}%
            </StatNumber>
          </Stat>
        </CardBody>
      </Card>
    </SimpleGrid>
  );
};

export default TaskStats;
