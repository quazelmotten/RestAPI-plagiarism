import React, { useState, useEffect, useRef } from 'react';
import { Card, CardBody, VStack, HStack, Heading, Text, Progress, Badge } from '@chakra-ui/react';
import api, { API_ENDPOINTS } from '../../services/api';

interface TaskProgressProps {
  taskId: string;
  status: string;
  cardBg?: string;
}

const stageConfig: Record<string, {
  phase: number;
  totalPhases: number;
  label: string;
  color: string;
  description: string;
  unit: string;
  unitPlural: string;
}> = {
  indexing: {
    phase: 1,
    totalPhases: 4,
    label: 'Indexing Files',
    color: 'blue',
    description: 'Tokenizing source files and building the fingerprint index',
    unit: 'file',
    unitPlural: 'files',
  },
  finding_intra_pairs: {
    phase: 2,
    totalPhases: 4,
    label: 'Finding Intra-Task Pairs',
    color: 'purple',
    description: 'Comparing files within this batch for similarities',
    unit: 'file checked',
    unitPlural: 'files checked',
  },
  finding_cross_pairs: {
    phase: 3,
    totalPhases: 4,
    label: 'Finding Cross-Task Pairs',
    color: 'pink',
    description: 'Comparing new files against previously submitted files',
    unit: 'file checked',
    unitPlural: 'files checked',
  },
  storing_results: {
    phase: 4,
    totalPhases: 4,
    label: 'Storing Results',
    color: 'orange',
    description: 'Persisting similarity scores to the database',
    unit: 'pair',
    unitPlural: 'pairs',
  },
};

const ACTIVE_STATUSES = ['indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'];

interface ProgressState {
  completed: number;
  total: number;
  percentage: number;
  status: string;
}

const TaskProgress: React.FC<TaskProgressProps> = ({ taskId, status: initialStatus, cardBg }) => {
  const [progress, setProgress] = useState<ProgressState>({
    completed: 0, total: 0, percentage: 0, status: initialStatus,
  });

  const statusRef = useRef(initialStatus);
  statusRef.current = progress.status;

  // Poll for progress updates — only updates this component's state
  useEffect(() => {
    if (!ACTIVE_STATUSES.includes(progress.status)) return;

    const poll = async () => {
      try {
        const response = await api.get(API_ENDPOINTS.TASKS);
        const task = response.data.find((t: any) => t.task_id === taskId);
        if (task && ACTIVE_STATUSES.includes(task.status)) {
          setProgress({
            completed: task.progress?.completed ?? 0,
            total: task.progress?.total ?? 0,
            percentage: task.progress?.percentage ?? 0,
            status: task.status,
          });
        } else if (task && !ACTIVE_STATUSES.includes(task.status)) {
          // Task finished — update status to stop polling
          setProgress(prev => ({ ...prev, status: task.status, percentage: 100 }));
        }
      } catch { /* silent */ }
    };

    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [taskId, progress.status]);

  const stage = stageConfig[progress.status];
  if (!stage) return null;

  const hasProgress = progress.total > 0;
  const unit = progress.completed === 1 ? stage.unit : stage.unitPlural;

  return (
    <Card bg={cardBg} borderColor={`${stage.color}.300`} borderWidth={2}>
      <CardBody>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between">
            <HStack>
              <Badge colorScheme={stage.color} fontSize="sm" px={2} py={0.5}>
                Stage {stage.phase}/{stage.totalPhases}
              </Badge>
              <Heading size="sm" color={`${stage.color}.600`}>
                {stage.label}
              </Heading>
            </HStack>
            {hasProgress && (
              <Text fontWeight="bold" color={`${stage.color}.600`}>
                {progress.completed}/{progress.total} {unit}
              </Text>
            )}
          </HStack>

          {hasProgress ? (
            <>
              <Progress
                value={progress.percentage}
                max={100}
                colorScheme={stage.color}
                size="lg"
                borderRadius="full"
                hasStripe
                isAnimated
              />
              <HStack justify="space-between" fontSize="sm" color="gray.600">
                <Text>{progress.percentage.toFixed(1)}% complete</Text>
                <Text>{progress.total - progress.completed} remaining</Text>
              </HStack>
            </>
          ) : (
            <Progress
              size="lg"
              colorScheme={stage.color}
              borderRadius="full"
              isIndeterminate
            />
          )}

          <Text fontSize="xs" color="gray.500" textAlign="center">
            {stage.description}
          </Text>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default TaskProgress;
