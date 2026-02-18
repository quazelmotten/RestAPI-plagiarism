import React, { useState, useEffect } from 'react';
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
  Spinner,
  VStack,
  HStack,
  Divider,
  useColorModeValue,
} from '@chakra-ui/react';
import { FiFileText, FiClock, FiAlertCircle, FiActivity, FiLayers } from 'react-icons/fi';
import api from '../services/api';

interface Task {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_pairs: number;
  files: { id: string; filename: string }[];
  results: Array<{
    ast_similarity: number;
  }>;
  created_at?: string;
  updated_at?: string;
  progress?: {
    completed: number;
    total: number;
  };
}

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
      return <FiActivity />;
    case 'failed':
      return <FiAlertCircle />;
    default:
      return <FiClock />;
  }
};

const formatTimeAgo = (date: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
};

const Overview: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  
  useEffect(() => {
    fetchTasks();
  }, []);
  
  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await api.get('/plagiarism/tasks');
      
      if (!Array.isArray(response.data)) {
        console.error('Expected array from /plagiarism/tasks, got:', typeof response.data);
        setTasks([]);
        return;
      }
      
      // Fetch detailed results for each task
      const tasksWithDetails = await Promise.all(
        response.data.map(async (task: Task) => {
          try {
            const detailsResponse = await api.get(`/plagiarism/${task.task_id}/results`);
            return detailsResponse.data;
          } catch (err) {
            console.error('Failed to fetch details for task', task.task_id, err);
            return null;
          }
        })
      );
      
      setTasks(tasksWithDetails.filter(Boolean));
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
    } finally {
      setLoading(false);
    }
  };
  
  // Calculate statistics
  const totalSubmissions = tasks.length;
  const pendingChecks = tasks.filter(t => t.status === 'pending' || t.status === 'processing').length;
  const highSimilarity = tasks.reduce((count, task) => {
    return count + (task.results?.filter(r => (r.ast_similarity || 0) >= 0.8).length || 0);
  }, 0);
  const totalFiles = tasks.reduce((sum, task) => sum + (task.files?.length || 0), 0);
  
  // Get recent activity (last 7 days or max 25 entries)
  const getRecentActivity = (): ActivityItem[] => {
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    
    const activity = tasks
      .filter(task => task.created_at)
      .map(task => ({
        id: task.task_id,
        timestamp: new Date(task.created_at!),
        filesCount: task.files?.length || 0,
        pairsCount: task.total_pairs || 0,
        status: task.status,
      }))
      .filter(item => item.timestamp >= oneWeekAgo)
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, 25);
    
    return activity;
  };
  
  const recentActivity = getRecentActivity();
  
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" h="400px">
        <Spinner size="xl" color="blue.500" />
      </Box>
    );
  }
  
  return (
    <Box>
      <Heading mb={6}>Dashboard Overview</Heading>
      
      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6} mb={8}>
        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiFileText color="var(--chakra-colors-blue-500)" />
                <StatLabel>Total Tasks</StatLabel>
              </HStack>
              <StatNumber color="blue.500">{totalSubmissions}</StatNumber>
              <Text fontSize="sm" color="gray.500">
                {totalFiles} files analyzed
              </Text>
            </Stat>
          </CardBody>
        </Card>
        
        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiClock color="var(--chakra-colors-orange-500)" />
                <StatLabel>Pending Checks</StatLabel>
              </HStack>
              <StatNumber color="orange.500">{pendingChecks}</StatNumber>
              <Text fontSize="sm" color="gray.500">
                {tasks.filter(t => t.status === 'processing').length} processing
              </Text>
            </Stat>
          </CardBody>
        </Card>
        
        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiAlertCircle color="var(--chakra-colors-red-500)" />
                <StatLabel>High Similarity</StatLabel>
              </HStack>
              <StatNumber color="red.500">{highSimilarity}</StatNumber>
              <Text fontSize="sm" color="gray.500">
                ≥80% similarity detected
              </Text>
            </Stat>
          </CardBody>
        </Card>
        
        <Card bg={cardBg}>
          <CardBody>
            <Stat>
              <HStack mb={2}>
                <FiLayers color="var(--chakra-colors-green-500)" />
                <StatLabel>Completed Tasks</StatLabel>
              </HStack>
              <StatNumber color="green.500">
                {tasks.filter(t => t.status === 'completed').length}
              </StatNumber>
              <Text fontSize="sm" color="gray.500">
                Ready for review
              </Text>
            </Stat>
          </CardBody>
        </Card>
      </SimpleGrid>

      <Card bg={cardBg} borderColor={borderColor}>
        <CardBody>
          <Heading size="md" mb={4}>Recent Activity</Heading>
          <Text fontSize="sm" color="gray.500" mb={4}>
            Showing activity from the last 7 days (max 25 entries)
          </Text>
          
          {recentActivity.length === 0 ? (
            <Text color="gray.500" textAlign="center" py={8}>
              No recent activity. Upload files to get started!
            </Text>
          ) : (
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
                            Task {item.id.substring(0, 8)}...
                          </Text>
                          <Badge
                            size="sm"
                            colorScheme={getStatusColor(item.status)}
                          >
                            {item.status}
                          </Badge>
                        </HStack>
                        <Text fontSize="xs" color="gray.500">
                          {item.filesCount} files • {item.pairsCount} pairs
                        </Text>
                      </VStack>
                      <Text fontSize="xs" color="gray.400">
                        {formatTimeAgo(item.timestamp)}
                      </Text>
                    </HStack>
                  </Box>
                  {index < recentActivity.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </VStack>
          )}
        </CardBody>
      </Card>
    </Box>
  );
};

export default Overview;
