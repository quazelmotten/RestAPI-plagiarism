import React, { useMemo } from 'react';
import {
  Box,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Card,
  CardBody,
  Heading,
  Text,
  Badge,
  Skeleton,
  SkeletonText,
  VStack,
  HStack,
  Divider,
  useColorModeValue,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiFileText, FiClock, FiAlertCircle, FiActivity, FiLayers } from 'react-icons/fi';
import { useTasks, type Task } from '../hooks/useTasks';

interface ActivityItem {
  id: string;
  timestamp: Date;
  filesCount: number;
  pairsCount: number;
  status: string;
}

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'completed': return 'green';
    case 'processing': return 'orange';
    case 'indexing': return 'blue';
    case 'finding_pairs': return 'purple';
    case 'pending': return 'yellow';
    case 'failed': return 'red';
    default: return 'gray';
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <FiFileText />;
    case 'processing':
    case 'indexing':
    case 'finding_pairs':
      return <FiActivity />;
    case 'failed':
      return <FiAlertCircle />;
    default:
      return <FiClock />;
  }
};

const formatTimeAgo = (date: Date, t: (key: string, options?: { count: number }) => string): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return t('justNow');
  if (diffMins < 60) return t('minAgo', { count: diffMins });
  if (diffHours < 24) return t('hourAgo', { count: diffHours });
  if (diffDays < 7) return t('dayAgo', { count: diffDays });
  return date.toLocaleDateString();
};

const Overview: React.FC = () => {
  const { t } = useTranslation(['overview', 'common']);
  const { data, isLoading } = useTasks();
  const tasks = data?.items ?? [];

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');

  const totalSubmissions = tasks.length;
  const activeStatuses = ['pending', 'indexing', 'finding_pairs', 'processing'];
  const pendingChecks = tasks.filter(t => activeStatuses.includes(t.status)).length;
  const highSimilarity = tasks.reduce((sum, task) => sum + (task.high_similarity_count || 0), 0);
  const totalFiles = tasks.reduce((sum, task) => sum + (task.files_count || 0), 0);

  const recentActivity = useMemo(() => {
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

    return tasks
      .filter(task => task.created_at)
      .map(task => ({
        id: task.task_id,
        timestamp: new Date(task.created_at!),
        filesCount: task.files_count || 0,
        pairsCount: task.total_pairs || 0,
        status: task.status,
      }))
      .filter(item => item.timestamp >= oneWeekAgo)
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, 25);
  }, [tasks]);

  if (isLoading) {
    return (
      <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6} mb={8} flexShrink={0}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} bg={cardBg}>
              <CardBody>
                <SkeletonText noOfLines={3} spacing={3} />
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>
        <Card bg={cardBg} flex={1} minH={0}>
          <CardBody>
            <Skeleton height="30px" mb={4} />
            <SkeletonText noOfLines={8} spacing={4} />
          </CardBody>
        </Card>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">

      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6} mb={8} flexShrink={0}>
        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiFileText color="var(--chakra-colors-blue-500)" />
                <StatLabel>{t('totalTasks')}</StatLabel>
              </HStack>
              <StatNumber color="blue.500">{totalSubmissions}</StatNumber>
              <Text fontSize="sm" color="gray.500">
                {t('filesAnalyzed', { count: totalFiles })}
              </Text>
            </Stat>
          </CardBody>
        </Card>

        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiClock color="var(--chakra-colors-orange-500)" />
                <StatLabel>{t('pendingChecks')}</StatLabel>
              </HStack>
              <StatNumber color="orange.500">{pendingChecks}</StatNumber>
              <Text fontSize="sm" color="gray.500">
                {tasks.filter(t => t.status === 'processing').length} {t('processing')}
              </Text>
            </Stat>
          </CardBody>
        </Card>

        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiAlertCircle color="var(--chakra-colors-red-500)" />
                <StatLabel>{t('highSimilarity')}</StatLabel>
              </HStack>
              <StatNumber color="red.500">{highSimilarity}</StatNumber>
              <Text fontSize="sm" color="gray.500">
                ≥80% {t('similarityDetected')}
              </Text>
            </Stat>
          </CardBody>
        </Card>

        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiLayers color="var(--chakra-colors-green-500)" />
                <StatLabel>{t('completedTasks')}</StatLabel>
              </HStack>
              <StatNumber color="green.500">
                {tasks.filter(t => t.status === 'completed').length}
              </StatNumber>
              <Text fontSize="sm" color="gray.500">
                {t('readyForReview')}
              </Text>
            </Stat>
          </CardBody>
        </Card>
      </SimpleGrid>

      <Card bg={cardBg} borderColor={borderColor} flex={1} minH={0} display="flex" flexDirection="column" overflow="hidden">
        <CardBody display="flex" flexDirection="column" minH={0} overflow="hidden">
          <Heading size="md" mb={4} flexShrink={0}>{t('recentActivity')}</Heading>
          <Text fontSize="sm" color="gray.500" mb={4} flexShrink={0}>
            {t('activityNote')}
          </Text>

          {recentActivity.length === 0 ? (
            <Text color="gray.500" textAlign="center" py={8}>
              {t('noActivity')}
            </Text>
          ) : (
            <Box flex={1} minH={0} overflowY="auto">
              <VStack align="stretch" spacing={3}>
              {recentActivity.map((item, index) => (
                <React.Fragment key={item.id}>
                  <Box
                    p={3}
                    borderRadius="md"
                    _hover={{ bg: hoverBg }}
                    transition="background 0.2s"
                  >
                    <HStack justify="space-between" align="start">
                      <VStack align="start" spacing={1} flex={1}>
                        <HStack spacing={2}>
                          {getStatusIcon(item.status)}
                          <Text fontWeight="medium" fontSize="sm">
                            {t('taskId', { id: item.id.substring(0, 8) })}...
                          </Text>
                          <Badge
                            size="sm"
                            colorScheme={getStatusColor(item.status)}
                          >
                            {item.status}
                          </Badge>
                        </HStack>
                        <Text fontSize="xs" color="gray.500">
                          {item.filesCount} {t('files')} • {item.pairsCount} {t('pairs')}
                        </Text>
                      </VStack>
                      <Text fontSize="xs" color="gray.400">
                        {formatTimeAgo(item.timestamp, t)}
                      </Text>
                    </HStack>
                  </Box>
                  {index < recentActivity.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </VStack>
            </Box>
          )}
        </CardBody>
      </Card>
    </Box>
  );
};

export default Overview;
