import React from 'react';
import { Card, CardBody, VStack, HStack, Heading, Text, Progress } from '@chakra-ui/react';
import type { TaskDetails } from '../../types';

interface TaskProgressProps {
  selectedTask: TaskDetails;
  cardBg?: string;
}

const TaskProgress: React.FC<TaskProgressProps> = ({ selectedTask, cardBg }) => {
  if (selectedTask.status !== 'processing' || !selectedTask.progress) return null;

  return (
    <Card bg={cardBg} borderColor="orange.300" borderWidth={2}>
      <CardBody>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between">
            <Heading size="sm" color="orange.600">
              Processing Task...
            </Heading>
            <Text fontWeight="bold" color="orange.600">
              {selectedTask.progress.display}
            </Text>
          </HStack>
          <Progress
            value={selectedTask.progress.percentage}
            max={100}
            colorScheme="orange"
            size="lg"
            borderRadius="full"
            hasStripe
            isAnimated
          />
          <HStack justify="space-between" fontSize="sm" color="gray.600">
            <Text>{selectedTask.progress.completed} comparisons completed</Text>
            <Text>{selectedTask.progress.total} total to analyze</Text>
          </HStack>
          <Text fontSize="xs" color="gray.500" textAlign="center">
            Using inverted index to skip non-viable candidates below 15% similarity threshold
          </Text>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default TaskProgress;
