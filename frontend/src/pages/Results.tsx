import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Heading,
  SimpleGrid,
  Card,
  CardBody,
  Text,
  Badge,
  Button,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  VStack,
  HStack,
  Tooltip,
  Select,
  Spinner,
  Alert,
  AlertIcon,
  useColorModeValue,
  Grid,
  GridItem,
  Flex,
} from '@chakra-ui/react';
import { 
  FiCheckCircle, 
  FiAlertCircle, 
  FiActivity,
  FiLayers,
  FiArrowLeft,
  FiRefreshCw
} from 'react-icons/fi';
import api from '../services/api';

interface PlagiarismMatch {
  file_a_start_line: number;
  file_a_end_line: number;
  file_b_start_line: number;
  file_b_end_line: number;
}

interface PlagiarismResult {
  file_a: {
    id: string;
    filename: string;
  };
  file_b: {
    id: string;
    filename: string;
  };
  ast_similarity: number;
  matches: PlagiarismMatch[];
  created_at: string;
}

interface Task {
  task_id: string;
  status: string;
  total_pairs: number;
  files: { id: string; filename: string }[];
  results: PlagiarismResult[];
  progress?: {
    completed: number;
    total: number;
    percentage: number;
    display: string;
  };
  overall_stats?: {
    avg_similarity: number;
    high: number;
    medium: number;
    low: number;
    total_results: number;
  };
}

interface FileContent {
  id: string;
  filename: string;
  content: string;
  language: string;
}

const getSimilarityColor = (similarity: number) => {
  if (similarity >= 0.8) return 'red';
  if (similarity >= 0.5) return 'orange';
  if (similarity >= 0.3) return 'yellow';
  return 'green';
};

const getSimilarityGradient = (similarity: number) => {
  if (similarity >= 0.8) return 'linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%)';
  if (similarity >= 0.5) return 'linear-gradient(135deg, #ffa726 0%, #fb8c00 100%)';
  if (similarity >= 0.3) return 'linear-gradient(135deg, #ffca28 0%, #ffb300 100%)';
  return 'linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)';
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <FiCheckCircle color="#48bb78" />;
    case 'failed':
      return <FiAlertCircle color="#f56565" />;
    case 'processing':
      return <FiActivity color="#ed8936" />;
    default:
      return <FiLayers color="#a0aec0" />;
  }
};

const Results: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'cards' | 'heatmap'>('cards');
  const [selectedTaskDetails, setSelectedTaskDetails] = useState<Task | null>(null);
  const [loadingTaskDetails, setLoadingTaskDetails] = useState(false);
  const [loadingMoreResults, setLoadingMoreResults] = useState(false);
  
  // Compare mode state
  const [compareMode, setCompareMode] = useState(false);
  const [selectedPair, setSelectedPair] = useState<PlagiarismResult | null>(null);
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  
  // Ref to store tasks for interval check
  const tasksRef = useRef(tasks);
  tasksRef.current = tasks;
  
  useEffect(() => {
    fetchTasks();
  }, []);
  
  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await api.get('/plagiarism/tasks');
      const taskList = response.data;
      
      if (!Array.isArray(taskList)) {
        console.error('Expected array from /plagiarism/tasks, got:', typeof taskList, taskList);
        setError('Invalid data format received from server');
        setTasks([]);
        return;
      }
      
      // Transform to Task format with empty files and results
      const tasks: Task[] = taskList.map((t: any) => ({
        task_id: t.task_id,
        status: t.status,
        total_pairs: t.progress?.total || 0,
        files: [],
        results: [],
        progress: t.progress
      }));
      
      setTasks(tasks);
      
      if (tasks.length > 0 && !selectedTaskId) {
        setSelectedTaskId(tasks[0].task_id);
      }
    } catch (err) {
      setError('Failed to fetch plagiarism tasks');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  
  const fetchTaskDetails = async (offset: number, isLoadMore: boolean = false) => {
    if (!selectedTaskId) return;
    try {
      if (!isLoadMore) {
        setLoadingTaskDetails(true);
        setSelectedTaskDetails(null);
      } else {
        setLoadingMoreResults(true);
      }
      
      const response = await api.get(`/plagiarism/${selectedTaskId}/results`, {
        params: {
          limit: 50,
          offset
        }
      });
      const data = response.data;
      
      const taskDetails: Task = {
        task_id: data.task_id,
        status: data.status,
        total_pairs: data.total_pairs,
        files: data.files,
        results: data.results,
        progress: {
          completed: data.progress.completed,
          total: data.progress.total,
          percentage: data.progress.percentage,
          display: data.progress.display,
        },
        overall_stats: data.overall_stats
      };
      
      if (offset === 0) {
        setSelectedTaskDetails(taskDetails);
      } else {
        setSelectedTaskDetails(prev => prev ? { ...prev, results: [...prev.results, ...data.results] } : null);
      }
    } catch (err) {
      console.error('Failed to fetch task details:', err);
    } finally {
      if (!isLoadMore) {
        setLoadingTaskDetails(false);
      } else {
        setLoadingMoreResults(false);
      }
    }
  };
  
  useEffect(() => {
    if (selectedTaskId) {
      fetchTaskDetails(0);
    } else {
      setSelectedTaskDetails(null);
    }
  }, [selectedTaskId]);
  
  const selectedTaskListItem = tasks.find(t => t.task_id === selectedTaskId);
  const selectedTask = selectedTaskDetails;

  const getStats = () => {
    if (!selectedTask) return { high: 0, medium: 0, low: 0, avg: 0 };
    
    // Use overall_stats from API if available (accurate for whole task)
    if (selectedTask.overall_stats) {
      return {
        high: selectedTask.overall_stats.high,
        medium: selectedTask.overall_stats.medium,
        low: selectedTask.overall_stats.low,
        avg: selectedTask.overall_stats.avg_similarity
      };
    }
    
    // Fallback: compute from loaded results only (partial)
    if (!selectedTask.results) return { high: 0, medium: 0, low: 0, avg: 0 };
    
    const similarities = selectedTask.results.map(r => r.ast_similarity || 0);
    const high = similarities.filter(s => s >= 0.8).length;
    const medium = similarities.filter(s => s >= 0.5 && s < 0.8).length;
    const low = similarities.filter(s => s < 0.5).length;
    const avg = similarities.length > 0 
      ? similarities.reduce((a, b) => a + b, 0) / similarities.length 
      : 0;
    
    return { high, medium, low, avg };
  };
  
  const stats = getStats();
  
  const renderHeatmap = () => {
    if (!selectedTask || selectedTask.files.length < 2) return null;
    
    const files = selectedTask.files;
    const matrix: number[][] = [];
    
    for (let i = 0; i < files.length; i++) {
      matrix[i] = [];
      for (let j = 0; j < files.length; j++) {
        if (i === j) {
          matrix[i][j] = 1;
        } else {
          const result = selectedTask.results.find(
            r => (r.file_a.id === files[i].id && r.file_b.id === files[j].id) ||
                 (r.file_a.id === files[j].id && r.file_b.id === files[i].id)
          );
          matrix[i][j] = result ? (result.ast_similarity || 0) : 0;
        }
      }
    }
    
    return (
      <Box overflowX="auto">
        <Grid 
          templateColumns={`repeat(${files.length + 1}, minmax(80px, 1fr))`}
          gap={2}
          p={4}
        >
          {/* Header row */}
          <GridItem />
          {files.map((file, idx) => (
            <GridItem key={idx}>
              <Text 
                fontSize="xs" 
                fontWeight="semibold" 
                textAlign="center"
                noOfLines={2}
                h="40px"
              >
                {file.filename}
              </Text>
            </GridItem>
          ))}
          
          {/* Data rows */}
          {files.map((fileA, i) => (
            <React.Fragment key={i}>
              <GridItem display="flex" alignItems="center">
                <Text 
                  fontSize="xs" 
                  fontWeight="semibold"
                  noOfLines={2}
                >
                  {fileA.filename}
                </Text>
              </GridItem>
              {files.map((fileB, j) => (
                <GridItem key={j}>
                  <Tooltip 
                    label={i === j ? fileA.filename : `${fileA.filename} vs ${fileB.filename}: ${(matrix[i][j] * 100).toFixed(1)}%`}
                    placement="top"
                  >
                    <Box
                      w="100%"
                      h="100%"
                      minH="60px"
                      bg={i === j ? 'gray.200' : getSimilarityGradient(matrix[i][j])}
                      color={i === j ? 'gray.500' : 'white'}
                      display="flex"
                      alignItems="center"
                      justifyContent="center"
                      fontSize="sm"
                      fontWeight="bold"
                      borderRadius="md"
                      cursor={i === j ? 'default' : 'pointer'}
                      opacity={i === j ? 0.5 : 1}
                      onClick={() => {
                        if (i !== j) {
                          const result = selectedTask?.results.find(
                            r => (r.file_a.id === files[i].id && r.file_b.id === files[j].id) ||
                                 (r.file_a.id === files[j].id && r.file_b.id === files[i].id)
                          );
                          if (result) handleCompare(result);
                        }
                      }}
                    >
                      {i === j ? '—' : `${(matrix[i][j] * 100).toFixed(0)}%`}
                    </Box>
                  </Tooltip>
                </GridItem>
              ))}
            </React.Fragment>
          ))}
        </Grid>
      </Box>
    );
  };
  
  const handleCompare = async (result: PlagiarismResult) => {
    setSelectedPair(result);
    setCompareMode(true);
    setLoadingContent(true);
    
    try {
      const [fileAResponse, fileBResponse] = await Promise.all([
        api.get(`/plagiarism/files/${result.file_a.id}/content`).catch(() => null),
        api.get(`/plagiarism/files/${result.file_b.id}/content`).catch(() => null)
      ]);
      
      if (fileAResponse?.data) setFileAContent(fileAResponse.data);
      if (fileBResponse?.data) setFileBContent(fileBResponse.data);
    } catch (err) {
      console.error('Error fetching file contents:', err);
    } finally {
      setLoadingContent(false);
    }
  };
  
  const handleBackToResults = () => {
    setCompareMode(false);
    setSelectedPair(null);
    setFileAContent(null);
    setFileBContent(null);
  };
  
  // Color mode values
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const selectedBg = useColorModeValue('blue.50', 'blue.900');
  const codeBg = useColorModeValue('gray.50', 'gray.800');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const matchBg = useColorModeValue('gray.50', 'gray.700');
  
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" h="400px">
        <Spinner size="xl" color="blue.500" />
      </Box>
    );
  }
  
  if (error) {
    return (
      <Alert status="error">
        <AlertIcon />
        {error}
      </Alert>
    );
  }
  
  return (
    <Box>
      <Heading mb={6}>Plagiarism Results</Heading>
      
      {tasks.length === 0 ? (
        <Card bg={cardBg}>
          <CardBody>
            <Text textAlign="center" color="gray.500" py={8}>
              No plagiarism checks found. Upload files to get started!
            </Text>
          </CardBody>
        </Card>
      ) : (
        <VStack spacing={6} align="stretch">
          {/* Task Selector */}
          <Card bg={cardBg}>
            <CardBody>
              <HStack justify="space-between" wrap="wrap" spacing={4}>
                <HStack>
                  <Text fontWeight="semibold">Select Task:</Text>
                  <Select
                    value={selectedTaskId}
                    onChange={(e) => setSelectedTaskId(e.target.value)}
                    w="400px"
                  >
                    {tasks.map((task) => (
                      <option key={task.task_id} value={task.task_id}>
                        {task.task_id.substring(0, 8)}... ({task.status}) - {task.progress?.display || `${task.total_pairs} pairs`}
                      </option>
                    ))}
                  </Select>
                  {selectedTaskListItem?.status === 'processing' && (
                    <Spinner size="sm" color="orange.500" speed="0.8s" />
                  )}
                  <Button
                    size="sm"
                    leftIcon={<FiRefreshCw />}
                    onClick={fetchTasks}
                    isLoading={loading}
                  >
                    Refresh
                  </Button>
                </HStack>
                
                <HStack>
                  <Text fontWeight="semibold">View:</Text>
                  <Select
                    value={viewMode}
                    onChange={(e) => setViewMode(e.target.value as 'cards' | 'heatmap')}
                    w="150px"
                  >
                    <option value="cards">Cards</option>
                    <option value="heatmap">Heatmap</option>
                  </Select>
                </HStack>
              </HStack>
            </CardBody>
          </Card>
          
          {selectedTask ? (
            <>
              {/* Statistics */}
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
                        <Badge colorScheme={selectedTask.status === 'completed' ? 'green' : selectedTask.status === 'processing' ? 'orange' : 'yellow'}>
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
                      <StatNumber color={getSimilarityColor(stats.avg)}>
                        {(stats.avg * 100).toFixed(1)}%
                      </StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
              </SimpleGrid>
              
              {/* Task Progress */}
              {selectedTask.status === 'processing' && selectedTask.progress && (
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
              )}
              
              {/* Similarity Distribution */}
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
                        max={selectedTask.total_pairs || 1} 
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
                        max={selectedTask.total_pairs || 1} 
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
                        max={selectedTask.total_pairs || 1} 
                        colorScheme="green" 
                        borderRadius="full"
                      />
                    </Box>
                  </VStack>
                </CardBody>
              </Card>
              
              {/* Results View */}
              {viewMode === 'heatmap' && selectedTask.files.length > 1 ? (
                <Card bg={cardBg}>
                  <CardBody>
                    <Heading size="sm" mb={4}>Similarity Heatmap</Heading>
                    {renderHeatmap()}
                  </CardBody>
                </Card>
              ) : (
                <Card bg={cardBg}>
                  <CardBody>
                    <HStack justify="space-between" align="center" mb={4}>
                      <Heading size="md">Top Similarities</Heading>
                      <HStack>
                        <Text color="gray.500" fontSize="sm">
                          {selectedTask.overall_stats?.total_results || selectedTask.results.length} pairs analyzed
                        </Text>
                        {selectedTask.status === 'processing' && (
                          <Badge colorScheme="orange" size="sm">
                            Processing...
                          </Badge>
                        )}
                      </HStack>
                    </HStack>
                    
                    <VStack align="stretch" spacing={2}>
                      {selectedTask.results
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
                    
                    {selectedTask.results.length < selectedTask.total_pairs && (
                      <Box textAlign="center" mt={4}>
                        <Button 
                          onClick={() => fetchTaskDetails(selectedTask.results.length, true)}
                          isLoading={loadingMoreResults}
                          loadingText="Loading..."
                        >
                          Load More Results
                        </Button>
                      </Box>
                    )}
                  </CardBody>
                </Card>
              )}
            </>
          ) : loadingTaskDetails ? (
            <Box textAlign="center" py={8}>
              <Spinner size="lg" />
            </Box>
          ) : null}
        </VStack>
      )}
    </Box>
  );
};

export default Results;