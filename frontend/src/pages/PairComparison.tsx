import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Heading,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Button,
  Spinner,
  Alert,
  AlertIcon,
  HStack,
  VStack,
  Text,
  Card,
  CardBody,
  Progress,
  useColorModeValue,
  Flex,
  Tooltip,
} from '@chakra-ui/react';
import { FiArrowLeft, FiEye, FiChevronUp, FiChevronDown } from 'react-icons/fi';
import api from '../services/api';

interface FileInfo {
  id: string;
  filename: string;
}

interface PlagiarismMatch {
  file_a_start_line: number;
  file_a_end_line: number;
  file_b_start_line: number;
  file_b_end_line: number;
}

interface PairResult {
  id: string;
  file_a: FileInfo;
  file_b: FileInfo;
  token_similarity: number;
  ast_similarity: number;
  matches: PlagiarismMatch[];
  created_at: string;
  task_id: string;
}

interface FileContent {
  id: string;
  filename: string;
  content: string;
  language: string;
}

type SortField = 'file_a' | 'file_b' | 'ast_similarity' | 'token_similarity' | 'created_at';
type SortDirection = 'asc' | 'desc';

const getSimilarityColor = (similarity: number): string => {
  if (similarity >= 0.8) return 'red';
  if (similarity >= 0.5) return 'orange';
  if (similarity >= 0.3) return 'yellow';
  return 'green';
};

const getSimilarityGradient = (similarity: number): string => {
  if (similarity >= 0.8) return 'linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%)';
  if (similarity >= 0.5) return 'linear-gradient(135deg, #ffa726 0%, #fb8c00 100%)';
  if (similarity >= 0.3) return 'linear-gradient(135deg, #ffca28 0%, #ffb300 100%)';
  return 'linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)';
};

const PairComparison: React.FC = () => {
  const [pairs, setPairs] = useState<PairResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const codeBg = useColorModeValue('gray.50', 'gray.800');
  const [selectedPair, setSelectedPair] = useState<PairResult | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  
  const [sortField, setSortField] = useState<SortField>('ast_similarity');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const selectedBg = useColorModeValue('blue.50', 'blue.900');

  useEffect(() => {
    fetchAllPairs();
  }, []);

  const fetchAllPairs = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get('/plagiarism/results/all');
      setPairs(response.data || []);
    } catch (err) {
      console.error('Error fetching pairs:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch pairs';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async (pair: PairResult) => {
    setSelectedPair(pair);
    setCompareMode(true);
    setLoadingContent(true);

    try {
      const [fileAResponse, fileBResponse] = await Promise.all([
        api.get(`/plagiarism/files/${pair.file_a.id}/content`).catch(() => null),
        api.get(`/plagiarism/files/${pair.file_b.id}/content`).catch(() => null)
      ]);

      if (fileAResponse?.data) setFileAContent(fileAResponse.data);
      if (fileBResponse?.data) setFileBContent(fileBResponse.data);
    } catch (error) {
      console.error('Error fetching file contents:', error);
    } finally {
      setLoadingContent(false);
    }
  };

  const handleBackToList = () => {
    setCompareMode(false);
    setSelectedPair(null);
    setFileAContent(null);
    setFileBContent(null);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const sortedPairs = useMemo(() => {
    return [...pairs].sort((a, b) => {
      let valueA: any;
      let valueB: any;
      
      switch (sortField) {
        case 'file_a':
          valueA = a.file_a.filename.toLowerCase();
          valueB = b.file_a.filename.toLowerCase();
          break;
        case 'file_b':
          valueA = a.file_b.filename.toLowerCase();
          valueB = b.file_b.filename.toLowerCase();
          break;
        case 'ast_similarity':
          valueA = a.ast_similarity || 0;
          valueB = b.ast_similarity || 0;
          break;
        case 'token_similarity':
          valueA = a.token_similarity || 0;
          valueB = b.token_similarity || 0;
          break;
        case 'created_at':
          valueA = new Date(a.created_at || 0).getTime();
          valueB = new Date(b.created_at || 0).getTime();
          break;
        default:
          return 0;
      }
      
      if (valueA < valueB) return sortDirection === 'asc' ? -1 : 1;
      if (valueA > valueB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [pairs, sortField, sortDirection]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? <FiChevronUp /> : <FiChevronDown />;
  };

  if (loading) {
    return (
      <Box p={8} textAlign="center">
        <Spinner size="xl" color="blue.500" thickness="4px" />
        <Text mt={4}>Loading pair comparisons...</Text>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={8}>
        <Alert status="error" mb={4}>
          <AlertIcon />
          {error}
        </Alert>
        <Button onClick={fetchAllPairs}>Retry</Button>
      </Box>
    );
  }

  if (compareMode && selectedPair) {
    return (
      <Flex h="calc(100vh - 150px)" gap={4}>
        {/* Compact Pair Table - Left Side */}
        <Box w="320px" flexShrink={0}>
          <Card h="100%" bg={bgColor} borderColor={borderColor}>
            <CardBody p={0}>
              <VStack align="stretch" h="100%" spacing={0}>
                <Box p={4} borderBottomWidth={1} borderColor={borderColor}>
                  <HStack justify="space-between">
                    <Heading size="sm">All Pairs ({pairs.length})</Heading>
                    <Button
                      size="sm"
                      leftIcon={<FiArrowLeft />}
                      onClick={handleBackToList}
                    >
                      Back
                    </Button>
                  </HStack>
                </Box>
                
                <Box overflowY="auto" flex={1} maxH="calc(100vh - 250px)">
                  <VStack align="stretch" spacing={1} p={2}>
                    {sortedPairs.map((pair) => (
                      <Box
                        key={pair.id}
                        p={3}
                        borderRadius="md"
                        cursor="pointer"
                        bg={selectedPair.id === pair.id ? selectedBg : 'transparent'}
                        _hover={{ bg: selectedPair.id === pair.id ? selectedBg : hoverBg }}
                        onClick={() => handleCompare(pair)}
                        borderWidth={1}
                        borderColor={selectedPair.id === pair.id ? 'blue.300' : borderColor}
                      >
                        <VStack align="stretch" spacing={1}>
                          <Text fontSize="xs" fontWeight="medium" noOfLines={1}>
                            {pair.file_a.filename}
                          </Text>
                          <Text fontSize="xs" color="gray.500" textAlign="center">
                            vs
                          </Text>
                          <Text fontSize="xs" fontWeight="medium" noOfLines={1}>
                            {pair.file_b.filename}
                          </Text>
                          <Box
                            mt={1}
                            p={1}
                            borderRadius="md"
                            bg={getSimilarityGradient(pair.ast_similarity || 0)}
                            color="white"
                            textAlign="center"
                          >
                            <Text fontSize="sm" fontWeight="bold">
                              {((pair.ast_similarity || 0) * 100).toFixed(1)}%
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
          <Card bg={bgColor}>
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
                              <Box key={index} p={3} bg={codeBg} borderRadius="md">
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

  return (
    <Box>
      <Heading mb={6}>Pair Comparison</Heading>
      
      {pairs.length === 0 ? (
        <Card>
          <CardBody>
            <Text textAlign="center" color="gray.500" py={8}>
              No plagiarism comparisons found. Upload files and run plagiarism checks to see pairs.
            </Text>
          </CardBody>
        </Card>
      ) : (
        <VStack spacing={6} align="stretch">
          <Card bg={bgColor}>
            <CardBody>
              <HStack justify="space-between" mb={4}>
                <Text color="gray.600">
                  Showing {pairs.length} file pair comparisons from all tasks
                </Text>
                <HStack>
                  <Text fontSize="sm" color="gray.500">Sort by:</Text>
                  <Button
                    size="sm"
                    variant={sortField === 'ast_similarity' ? 'solid' : 'ghost'}
                    colorScheme={sortField === 'ast_similarity' ? 'blue' : undefined}
                    onClick={() => handleSort('ast_similarity')}
                    rightIcon={<SortIcon field="ast_similarity" />}
                  >
                    Similarity
                  </Button>
                </HStack>
              </HStack>
              
              <Box overflowX="auto">
                <Table variant="simple" size="md">
                  <Thead>
                    <Tr>
                      <Th cursor="pointer" onClick={() => handleSort('file_a')}>
                        <HStack spacing={1}>
                          <Text>File A</Text>
                          <SortIcon field="file_a" />
                        </HStack>
                      </Th>
                      <Th cursor="pointer" onClick={() => handleSort('file_b')}>
                        <HStack spacing={1}>
                          <Text>File B</Text>
                          <SortIcon field="file_b" />
                        </HStack>
                      </Th>
                      <Th cursor="pointer" onClick={() => handleSort('ast_similarity')} isNumeric>
                        <HStack spacing={1} justify="flex-end">
                          <Text>AST Similarity</Text>
                          <SortIcon field="ast_similarity" />
                        </HStack>
                      </Th>
                      <Th cursor="pointer" onClick={() => handleSort('token_similarity')} isNumeric>
                        <HStack spacing={1} justify="flex-end">
                          <Text>Token Similarity</Text>
                          <SortIcon field="token_similarity" />
                        </HStack>
                      </Th>
                      <Th isNumeric>Matches</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {sortedPairs.map((pair) => (
                      <Tr key={pair.id} _hover={{ bg: hoverBg }}>
                        <Td>
                          <Text fontWeight="medium" noOfLines={1} maxW="200px">
                            {pair.file_a.filename}
                          </Text>
                        </Td>
                        <Td>
                          <Text fontWeight="medium" noOfLines={1} maxW="200px">
                            {pair.file_b.filename}
                          </Text>
                        </Td>
                        <Td isNumeric>
                          <Badge colorScheme={getSimilarityColor(pair.ast_similarity || 0)} fontSize="md">
                            {((pair.ast_similarity || 0) * 100).toFixed(1)}%
                          </Badge>
                        </Td>
                        <Td isNumeric>
                          <Text fontSize="sm" color="gray.600">
                            {((pair.token_similarity || 0) * 100).toFixed(1)}%
                          </Text>
                        </Td>
                        <Td isNumeric>
                          <Text fontSize="sm">{pair.matches?.length || 0}</Text>
                        </Td>
                        <Td>
                          <Tooltip label="Compare files">
                            <Button
                              size="sm"
                              leftIcon={<FiEye />}
                              onClick={() => handleCompare(pair)}
                            >
                              Compare
                            </Button>
                          </Tooltip>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            </CardBody>
          </Card>
          
          {/* Similarity Distribution */}
          <Card bg={bgColor}>
            <CardBody>
              <Heading size="sm" mb={4}>Similarity Distribution</Heading>
              {(() => {
                const similarities = pairs.map(p => p.ast_similarity || 0);
                const high = similarities.filter(s => s >= 0.8).length;
                const medium = similarities.filter(s => s >= 0.5 && s < 0.8).length;
                const low = similarities.filter(s => s < 0.5).length;
                const total = pairs.length || 1;
                
                return (
                  <VStack align="stretch" spacing={3}>
                    <Box>
                      <HStack justify="space-between" mb={1}>
                        <Text fontSize="sm">High (≥80%)</Text>
                        <Text fontSize="sm" fontWeight="bold" color="red.500">{high}</Text>
                      </HStack>
                      <Progress value={high} max={total} colorScheme="red" borderRadius="full" />
                    </Box>
                    <Box>
                      <HStack justify="space-between" mb={1}>
                        <Text fontSize="sm">Medium (50-79%)</Text>
                        <Text fontSize="sm" fontWeight="bold" color="orange.500">{medium}</Text>
                      </HStack>
                      <Progress value={medium} max={total} colorScheme="orange" borderRadius="full" />
                    </Box>
                    <Box>
                      <HStack justify="space-between" mb={1}>
                        <Text fontSize="sm">Low (&lt;50%)</Text>
                        <Text fontSize="sm" fontWeight="bold" color="green.500">{low}</Text>
                      </HStack>
                      <Progress value={low} max={total} colorScheme="green" borderRadius="full" />
                    </Box>
                  </VStack>
                );
              })()}
            </CardBody>
          </Card>
        </VStack>
      )}
    </Box>
  );
};

export default PairComparison;