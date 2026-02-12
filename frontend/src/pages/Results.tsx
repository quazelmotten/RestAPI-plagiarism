import React, { useState, useEffect } from 'react';
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
  Flex,
} from '@chakra-ui/react';
import { 
  FiFileText, 
  FiCheckCircle, 
  FiAlertCircle, 
  FiActivity,
  FiChevronDown,
  FiChevronUp,
  FiLayers,
  FiEye,
  FiArrowLeft
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
  token_similarity: number;
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
  
  // Compare mode state
  const [compareMode, setCompareMode] = useState(false);
  const [selectedPair, setSelectedPair] = useState<PlagiarismResult | null>(null);
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  
  // Color mode values
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const selectedBg = useColorModeValue('blue.50', 'blue.900');
  const codeBg = useColorModeValue('gray.50', 'gray.800');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const matchBg = useColorModeValue('gray.50', 'gray.700');
  
  useEffect(() => {
    fetchTasks();
  }, []);
  
  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await api.get('/plagiarism/tasks');
      const taskList = response.data;
      
      // Validate that taskList is an array
      if (!Array.isArray(taskList)) {
        console.error('Expected array from /plagiarism/tasks, got:', typeof taskList, taskList);
        setError('Invalid data format received from server');
        setTasks([]);
        return;
      }
      
      // Fetch detailed results for each task
      const tasksWithDetails = await Promise.all(
        taskList.map(async (task: Task) => {
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

  // Compare Mode UI
  if (compareMode && selectedPair && selectedTask) {
    return (
      <Flex h="calc(100vh - 150px)" gap={4}>
        {/* Compact Results List - Left Side */}
        <Box w="320px" flexShrink={0}>
          <Card h="100%" bg={cardBg} borderColor={borderColor}>
            <CardBody p={0}>
              <VStack align="stretch" h="100%" spacing={0}>
                <Box p={4} borderBottomWidth={1} borderColor={borderColor}>
                  <HStack justify="space-between">
                    <Heading size="sm">Results ({selectedTask.results.length})</Heading>
                    <Button
                      size="sm"
                      leftIcon={<FiArrowLeft />}
                      onClick={handleBackToResults}
                    >
                      Back
                    </Button>
                  </HStack>
                </Box>
                
                <Box overflowY="auto" flex={1} maxH="calc(100vh - 250px)">
                  <VStack align="stretch" spacing={1} p={2}>
                    {selectedTask.results
                      .sort((a, b) => (b.ast_similarity || 0) - (a.ast_similarity || 0))
                      .map((result, idx) => (
                        <Box
                          key={idx}
                          p={3}
                          borderRadius="md"
                          cursor="pointer"
                          bg={selectedPair.file_a.id === result.file_a.id && selectedPair.file_b.id === result.file_b.id ? selectedBg : 'transparent'}
                          _hover={{ bg: selectedPair.file_a.id === result.file_a.id && selectedPair.file_b.id === result.file_b.id ? selectedBg : hoverBg }}
                          onClick={() => handleCompare(result)}
                          borderWidth={1}
                          borderColor={selectedPair.file_a.id === result.file_a.id && selectedPair.file_b.id === result.file_b.id ? 'blue.300' : borderColor}
                        >
                          <VStack align="stretch" spacing={1}>
                            <Text fontSize="xs" fontWeight="medium" noOfLines={1}>
                              {result.file_a.filename}
                            </Text>
                            <Text fontSize="xs" color="gray.500" textAlign="center">
                              vs
                            </Text>
                            <Text fontSize="xs" fontWeight="medium" noOfLines={1}>
                              {result.file_b.filename}
                            </Text>
                            <Box
                              mt={1}
                              p={1}
                              borderRadius="md"
                              bg={getSimilarityGradient(result.ast_similarity || 0)}
                              color="white"
                              textAlign="center"
                            >
                              <Text fontSize="sm" fontWeight="bold">
                                {((result.ast_similarity || 0) * 100).toFixed(1)}%
                              </Text>
                            </Box>
                          </VStack>
                        </Box>
                      ))}
                  </VStack>
                </Box>
              </VStack>
            </CardBody>
          </Card>
        </Box>

        {/* Main Compare Window - Right Side */}
        <Box flex={1} overflow="auto">
          <Card bg={cardBg}>
            <CardBody>
              <VStack align="stretch" spacing={6}>
                {/* Header with Similarity */}
                <HStack justify="space-between">
                  <Heading size="lg">Compare Files</Heading>
                </HStack>
                
                <Card variant="outline">
                  <CardBody>
                    <VStack spacing={4}>
                      <HStack justify="space-between" w="100%">
                        <Text fontWeight="bold">{selectedPair.file_a.filename}</Text>
                        <Text color="gray.500">vs</Text>
                        <Text fontWeight="bold">{selectedPair.file_b.filename}</Text>
                      </HStack>
                      
                      <Box
                        w="100%"
                        p={6}
                        borderRadius="lg"
                        bg={getSimilarityGradient(selectedPair.ast_similarity || 0)}
                        color="white"
                        textAlign="center"
                      >
                        <Text fontSize="3xl" fontWeight="bold">
                          {((selectedPair.ast_similarity || 0) * 100).toFixed(1)}%
                        </Text>
                        <Text fontSize="sm">Similarity Score (AST)</Text>
                        <Text fontSize="xs" opacity={0.8}>
                          Token: {((selectedPair.token_similarity || 0) * 100).toFixed(1)}%
                        </Text>
                      </Box>
                      
                      <Text fontSize="sm" color="gray.600">
                        Matches: {selectedPair.matches?.length || 0} regions
                      </Text>
                    </VStack>
                  </CardBody>
                </Card>

                {/* File Contents */}
                {loadingContent ? (
                  <Box textAlign="center" py={8}>
                    <Spinner size="lg" />
                    <Text mt={2}>Loading file contents...</Text>
                  </Box>
                ) : (
                  <>
                    <Flex gap={4}>
                      {/* File A */}
                      <Card flex={1}>
                        <CardBody>
                          <VStack align="stretch" spacing={3}>
                            <HStack justify="space-between">
                              <Text fontWeight="bold">{selectedPair.file_a.filename}</Text>
                              <Badge colorScheme="blue">{fileAContent?.language || 'unknown'}</Badge>
                            </HStack>
                            <Box
                              bg={codeBg}
                              p={4}
                              borderRadius="md"
                              maxH="500px"
                              overflowY="auto"
                              fontFamily="monospace"
                              fontSize="sm"
                              whiteSpace="pre-wrap"
                            >
                              <Text>{fileAContent?.content || 'File content not available'}</Text>
                            </Box>
                          </VStack>
                        </CardBody>
                      </Card>

                      {/* File B */}
                      <Card flex={1}>
                        <CardBody>
                          <VStack align="stretch" spacing={3}>
                            <HStack justify="space-between">
                              <Text fontWeight="bold">{selectedPair.file_b.filename}</Text>
                              <Badge colorScheme="green">{fileBContent?.language || 'unknown'}</Badge>
                            </HStack>
                            <Box
                              bg={codeBg}
                              p={4}
                              borderRadius="md"
                              maxH="500px"
                              overflowY="auto"
                              fontFamily="monospace"
                              fontSize="sm"
                              whiteSpace="pre-wrap"
                            >
                              <Text>{fileBContent?.content || 'File content not available'}</Text>
                            </Box>
                          </VStack>
                        </CardBody>
                      </Card>
                    </Flex>

                    {/* Matches */}
                    {selectedPair.matches && selectedPair.matches.length > 0 && (
                      <Card>
                        <CardBody>
                          <Heading size="sm" mb={4}>Matching Regions</Heading>
                          <VStack align="stretch" spacing={3}>
                            {selectedPair.matches.map((match, index) => (
                              <Box key={index} p={3} bg={matchBg} borderRadius="md">
                                <Flex gap={4}>
                                  <Box flex={1}>
                                    <Text fontSize="sm" fontWeight="medium">{selectedPair.file_a.filename}</Text>
                                    <Text fontSize="sm">Lines {match.file_a_start_line} - {match.file_a_end_line}</Text>
                                  </Box>
                                  <Box flex={1}>
                                    <Text fontSize="sm" fontWeight="medium">{selectedPair.file_b.filename}</Text>
                                    <Text fontSize="sm">Lines {match.file_b_start_line} - {match.file_b_end_line}</Text>
                                  </Box>
                                </Flex>
                              </Box>
                            ))}
                          </VStack>
                        </CardBody>
                      </Card>
                    )}
                  </>
                )}
              </VStack>
            </CardBody>
          </Card>
        </Box>
      </Flex>
    );
  }
  
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
                        <SimilarityCard 
                          key={idx} 
                          result={result} 
                          cardBg={cardBg}
                          borderColor={borderColor}
                          matchBg={matchBg}
                          onCompare={() => handleCompare(result)}
                        />
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

interface SimilarityCardProps {
  result: PlagiarismResult;
  cardBg: string;
  borderColor: string;
  matchBg: string;
  onCompare: () => void;
}

const SimilarityCard: React.FC<SimilarityCardProps> = ({ result, cardBg, borderColor, matchBg, onCompare }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Card
      variant="outline"
      borderColor={borderColor}
      bg={cardBg}
      boxShadow="sm"
      _hover={{ boxShadow: 'md', transform: 'translateY(-2px)', cursor: 'pointer' }}
      transition="all 0.2s"
      onClick={onCompare}
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
          
          <Box 
            onClick={onCompare}
            cursor="pointer"
            p={2}
            borderRadius="md"
            _hover={{ bg: 'gray.100' }}
            textAlign="center"
          >
            <Text fontSize="sm" color="blue.500" fontWeight="medium">
              Click to view full comparison
            </Text>
          </Box>
          
          <Button 
            size="sm" 
            variant="ghost" 
            rightIcon={isOpen ? <FiChevronUp /> : <FiChevronDown />}
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(!isOpen);
            }}
          >
            {isOpen ? 'Hide Details' : 'View Matches'}
          </Button>
          
          <Collapse in={isOpen}>
            <Box 
              bg={matchBg}
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

export default Results;