import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import {
  Box,
  Heading,
  SimpleGrid,
  Card,
  CardBody,
  Text,
  Badge,
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
  Collapse,
  Button,
  useColorModeValue,
  Grid,
  GridItem,
} from '@chakra-ui/react';
import { 
  FiFileText, 
  FiCheckCircle, 
  FiAlertCircle, 
  FiActivity,
  FiChevronDown,
  FiChevronUp,
  FiLayers,
  FiEye
} from 'react-icons/fi';
import api from '../services/api';

interface PlagiarismResult {
  file_a: {
    id: string;
    filename: string;
  };
  file_b: {
    id: string;
    filename: string;
  };
  token_similarity: number;
  ast_similarity: number;
  matches: any[];
  created_at: string;
}

interface Task {
  task_id: string;
  status: string;
  total_pairs: number;
  files: { id: string; filename: string }[];
  results: PlagiarismResult[];
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

const SimilarityCard: React.FC<{ result: PlagiarismResult }> = ({ result }) => {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  
  return (
    <Card 
      variant="outline" 
      borderColor={borderColor}
      bg={bgColor}
      boxShadow="sm"
      _hover={{ boxShadow: 'md', transform: 'translateY(-2px)' }}
      transition="all 0.2s"
    >
      <CardBody>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between">
            <HStack spacing={2} flex={1}>
              <FiFileText />
              <Text fontWeight="semibold" fontSize="sm" noOfLines={1}>
                {result.file_a.filename}
              </Text>
            </HStack>
            <Text color="gray.500" fontSize="xs">vs</Text>
            <HStack spacing={2} flex={1} justify="flex-end">
              <Text fontWeight="semibold" fontSize="sm" noOfLines={1} textAlign="right">
                {result.file_b.filename}
              </Text>
              <FiFileText />
            </HStack>
          </HStack>
          
          <Box 
            p={4} 
            borderRadius="lg"
            bg={getSimilarityGradient(result.ast_similarity || 0)}
            color="white"
          >
            <VStack spacing={1}>
              <Text fontSize="2xl" fontWeight="bold">
                {((result.ast_similarity || 0) * 100).toFixed(1)}%
              </Text>
              <Text fontSize="xs" opacity={0.9}>Similarity Score</Text>
            </VStack>
          </Box>
          
          <HStack justify="space-between" fontSize="sm">
            <Text color="gray.600">
              Token: {((result.token_similarity || 0) * 100).toFixed(1)}%
            </Text>
            <Text color="gray.600">
              AST: {((result.ast_similarity || 0) * 100).toFixed(1)}%
            </Text>
          </HStack>
          
          <HStack spacing={2}>
            <Button 
              size="sm" 
              variant="ghost" 
              rightIcon={isOpen ? <FiChevronUp /> : <FiChevronDown />}
              onClick={() => setIsOpen(!isOpen)}
            >
              {isOpen ? 'Hide Details' : 'View Matches'}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<FiEye />}
              onClick={() => navigate(`/dashboard/compare/${result.file_a.id}/${result.file_b.id}`)}
            >
              Compare
            </Button>
          </HStack>
          
          <Collapse in={isOpen}>
            <Box 
              bg={useColorModeValue('gray.50', 'gray.700')} 
              p={3} 
              borderRadius="md"
              fontSize="sm"
            >
              {result.matches && result.matches.length > 0 ? (
                <VStack align="stretch" spacing={2}>
                  <Text fontWeight="semibold">Matching Blocks:</Text>
                  {result.matches.map((match, idx) => (
                    <HStack key={idx} justify="space-between" fontSize="xs">
                      <Text>
                        {result.file_a.filename}: Lines {match.file_a_start_line}-{match.file_a_end_line}
                      </Text>
                      <Text>
                        {result.file_b.filename}: Lines {match.file_b_start_line}-{match.file_b_end_line}
                      </Text>
                    </HStack>
                  ))}
                </VStack>
              ) : (
                <Text color="gray.500">No specific matches found</Text>
              )}
            </Box>
          </Collapse>
        </VStack>
      </CardBody>
    </Card>
  );
};

const HeatmapCell: React.FC<{ 
  similarity: number; 
  fileA: string; 
  fileB: string;
  isDiagonal?: boolean;
}> = ({ similarity, fileA, fileB, isDiagonal }) => {
  const bg = isDiagonal ? 'gray.200' : getSimilarityGradient(similarity);
  const color = isDiagonal ? 'gray.500' : 'white';
  
  return (
    <Tooltip 
      label={isDiagonal ? fileA : `${fileA} vs ${fileB}: ${(similarity * 100).toFixed(1)}%`}
      placement="top"
    >
      <Box
        w="100%"
        h="100%"
        minH="60px"
        bg={bg}
        color={color}
        display="flex"
        alignItems="center"
        justifyContent="center"
        fontSize="sm"
        fontWeight="bold"
        borderRadius="md"
        cursor={isDiagonal ? 'default' : 'pointer'}
        opacity={isDiagonal ? 0.5 : 1}
      >
        {isDiagonal ? '—' : `${(similarity * 100).toFixed(0)}%`}
      </Box>
    </Tooltip>
  );
};

const Results: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'cards' | 'heatmap'>('cards');
  
  const cardBg = useColorModeValue('white', 'gray.800');
  
  useEffect(() => {
    fetchTasks();
  }, []);
  
  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await api.get('/plagiarism/tasks');
      const taskList = response.data;
      
      // Fetch detailed results for each task
      const tasksWithDetails = await Promise.all(
        taskList.map(async (task: any) => {
          try {
            const detailsResponse = await api.get(`/plagiarism/${task.task_id}/results`);
            return detailsResponse.data;
          } catch (err) {
            console.error('Failed to fetch details for task %s', task.task_id, err);
            return null;
          }
        })
      );
      
      const validTasks = tasksWithDetails.filter(Boolean);
      setTasks(validTasks);
      
      if (validTasks.length > 0 && !selectedTaskId) {
        setSelectedTaskId(validTasks[0].task_id);
      }
    } catch (err) {
      setError('Failed to fetch plagiarism results');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  
  const selectedTask = tasks.find(t => t.task_id === selectedTaskId);
  
  const getStats = () => {
    if (!selectedTask || !selectedTask.results) return { high: 0, medium: 0, low: 0, avg: 0 };
    
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
                  <HeatmapCell
                    similarity={matrix[i][j]}
                    fileA={fileA.filename}
                    fileB={fileB.filename}
                    isDiagonal={i === j}
                  />
                </GridItem>
              ))}
            </React.Fragment>
          ))}
        </Grid>
      </Box>
    );
  };
  
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
        <Card>
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
                    w="300px"
                  >
                    {tasks.map((task) => (
                      <option key={task.task_id} value={task.task_id}>
                        {task.task_id.substring(0, 8)}... ({task.status}) - {task.total_pairs} pairs
                      </option>
                    ))}
                  </Select>
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
          
          {selectedTask && (
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
                        <Badge colorScheme={selectedTask.status === 'completed' ? 'green' : 'yellow'}>
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
                <>
                  <HStack justify="space-between" align="center">
                    <Heading size="md">Detailed Results</Heading>
                    <Text color="gray.500" fontSize="sm">
                      {selectedTask.results.length} pairs analyzed
                    </Text>
                  </HStack>
                  
                  <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                    {selectedTask.results
                      .sort((a, b) => (b.ast_similarity || 0) - (a.ast_similarity || 0))
                      .map((result, idx) => (
                        <SimilarityCard key={idx} result={result} />
                      ))}
                  </SimpleGrid>
                </>
              )}
            </>
          )}
        </VStack>
      )}
    </Box>
  );
};

export default Results;
