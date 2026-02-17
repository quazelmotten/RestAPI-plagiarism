import React, { useState, useEffect, useMemo, useRef, useCallback, useLayoutEffect } from 'react';
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
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
} from '@chakra-ui/react';
import { FiArrowLeft, FiChevronUp, FiChevronDown, FiCrosshair } from 'react-icons/fi';
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

interface LineInfo {
  lineNumber: number;
  content: string;
  matchIndex: number | null;
}

type SortField = 'file_a' | 'file_b' | 'ast_similarity' | 'token_similarity' | 'created_at';
type SortDirection = 'asc' | 'desc';

const MATCH_COLORS = [
  { bg: 'rgba(255, 235, 59, 0.4)', border: '#FBC02D', hover: 'rgba(255, 235, 59, 0.6)' },
  { bg: 'rgba(76, 175, 80, 0.3)', border: '#388E3C', hover: 'rgba(76, 175, 80, 0.5)' },
  { bg: 'rgba(33, 150, 243, 0.3)', border: '#1976D2', hover: 'rgba(33, 150, 243, 0.5)' },
  { bg: 'rgba(156, 39, 176, 0.3)', border: '#7B1FA2', hover: 'rgba(156, 39, 176, 0.5)' },
  { bg: 'rgba(255, 87, 34, 0.3)', border: '#E64A19', hover: 'rgba(255, 87, 34, 0.5)' },
  { bg: 'rgba(0, 188, 212, 0.3)', border: '#0097A7', hover: 'rgba(0, 188, 212, 0.5)' },
  { bg: 'rgba(233, 30, 99, 0.3)', border: '#C2185B', hover: 'rgba(233, 30, 99, 0.5)' },
  { bg: 'rgba(255, 152, 0, 0.3)', border: '#F57C00', hover: 'rgba(255, 152, 0, 0.5)' },
];

const getMatchColor = (matchIndex: number) => {
  return MATCH_COLORS[matchIndex % MATCH_COLORS.length];
};

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

const parseFileContent = (content: string, matches: PlagiarismMatch[], isFileA: boolean): LineInfo[] => {
  const lines = content.split('\n');
  return lines.map((line, index) => {
    const lineNumber = index + 1;
    let matchIndex: number | null = null;
    
    matches.forEach((match, idx) => {
      const startLine = isFileA ? match.file_a_start_line : match.file_b_start_line;
      const endLine = isFileA ? match.file_a_end_line : match.file_b_end_line;
      
      if (lineNumber >= startLine && lineNumber <= endLine) {
        matchIndex = idx;
      }
    });
    
    return {
      lineNumber,
      content: line,
      matchIndex,
    };
  });
};

interface FileViewerProps {
  lines: LineInfo[];
  fileName: string;
  language: string;
  hoveredMatchIndex: number | null;
  onHoverMatch: (matchIndex: number | null) => void;
  onScrollToMatch: (matchIndex: number) => void;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  lineRefs: React.MutableRefObject<(HTMLDivElement | null)[]>;
  isFileA: boolean;
}

const FileViewer: React.FC<FileViewerProps> = ({
  lines,
  fileName,
  language,
  hoveredMatchIndex,
  onHoverMatch,
  onScrollToMatch,
  scrollRef,
  lineRefs,
  isFileA,
}) => {
  const lineNumberBg = useColorModeValue('gray.100', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const lineNumberColor = useColorModeValue('gray.500', 'gray.400');
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  
  // Apply hover styles via CSS classes for immediate visual feedback
  useLayoutEffect(() => {
    if (!containerRef.current) return;
    
    const lines = containerRef.current.querySelectorAll('[data-match-index]');
    lines.forEach((line) => {
      const matchIdx = line.getAttribute('data-match-index');
      if (hoveredMatchIndex !== null && matchIdx === hoveredMatchIndex.toString()) {
        line.classList.add('match-hovered');
      } else {
        line.classList.remove('match-hovered');
      }
    });
  }, [hoveredMatchIndex]);
  
  const handleMouseEnter = useCallback((matchIndex: number | null) => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
    rafRef.current = requestAnimationFrame(() => {
      onHoverMatch(matchIndex);
    });
  }, [onHoverMatch]);
  
  const handleMouseLeave = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
    rafRef.current = requestAnimationFrame(() => {
      onHoverMatch(null);
    });
  }, [onHoverMatch]);
  
  const handleContextMenu = (e: React.MouseEvent, matchIndex: number | null) => {
    if (matchIndex !== null) {
      e.preventDefault();
      onScrollToMatch(matchIndex);
    }
  };

  return (
    <Card flex={1}>
      <CardBody>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between">
            <Text fontWeight="bold">{fileName}</Text>
            <Badge colorScheme={isFileA ? 'blue' : 'green'}>{language || 'unknown'}</Badge>
          </HStack>
          <Box
            ref={scrollRef}
            borderWidth={1}
            borderColor={borderColor}
            borderRadius="md"
            maxH="600px"
            overflowY="auto"
            fontFamily="monospace"
            fontSize="sm"
            className="file-viewer-container"
            sx={{
              '.match-line': {
                transition: 'background-color 0.08s ease-out',
              },
              '.match-line:hover': {
                filter: 'brightness(0.95)',
              },
              '.match-hovered': {
                filter: 'brightness(0.85) !important',
                boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.1)',
              },
            }}
          >
            <Box ref={containerRef}>
              {lines.map((line, idx) => {
                const color = line.matchIndex !== null ? getMatchColor(line.matchIndex) : null;
                const isHovered = line.matchIndex !== null && line.matchIndex === hoveredMatchIndex;
                const bgColor = isHovered && color ? color.hover : (color?.bg || 'transparent');
                const borderLeftColor = color?.border || 'transparent';
                
                return (
                  <Flex
                    key={idx}
                    ref={(el) => { lineRefs.current[idx] = el; }}
                    data-match-index={line.matchIndex}
                    className={line.matchIndex !== null ? 'match-line' : ''}
                    borderLeftWidth={line.matchIndex !== null ? 3 : 0}
                    borderLeftColor={borderLeftColor}
                    bg={bgColor}
                    onMouseEnter={() => handleMouseEnter(line.matchIndex)}
                    onMouseLeave={handleMouseLeave}
                    onContextMenu={(e) => handleContextMenu(e, line.matchIndex)}
                    cursor={line.matchIndex !== null ? 'pointer' : 'default'}
                  >
                    <Box
                      w="50px"
                      minW="50px"
                      bg={lineNumberBg}
                      textAlign="right"
                      pr={2}
                      py={0.5}
                      color={lineNumberColor}
                      fontSize="xs"
                      borderRightWidth={1}
                      borderRightColor={borderColor}
                      userSelect="none"
                    >
                      {line.lineNumber}
                    </Box>
                    <Box
                      flex={1}
                      pl={3}
                      py={0.5}
                      whiteSpace="pre"
                      overflow="hidden"
                      color={textColor}
                    >
                      {line.content || ' '}
                    </Box>
                  </Flex>
                );
              })}
            </Box>
          </Box>
        </VStack>
      </CardBody>
    </Card>
  );
};

const PairComparison: React.FC = () => {
  const [pairs, setPairs] = useState<PairResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const [selectedPair, setSelectedPair] = useState<PairResult | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [hoveredMatchIndex, setHoveredMatchIndex] = useState<number | null>(null);
  
  const fileAScrollRef = useRef<HTMLDivElement>(null);
  const fileBScrollRef = useRef<HTMLDivElement>(null);
  const fileALineRefs = useRef<(HTMLDivElement | null)[]>([]);
  const fileBLineRefs = useRef<(HTMLDivElement | null)[]>([]);
  
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

      if (!Array.isArray(response.data)) {
        console.error('Expected array from /plagiarism/results/all, got:', typeof response.data, response.data);
        setError('Invalid data format received from server');
        setPairs([]);
        return;
      }

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
    setHoveredMatchIndex(null);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const handleScrollToMatch = useCallback((matchIndex: number, targetIsFileA: boolean) => {
    if (!selectedPair) return;
    
    const match = selectedPair.matches[matchIndex];
    if (!match) return;
    
    if (targetIsFileA) {
      const targetLineIndex = match.file_a_start_line - 1;
      const targetElement = fileALineRefs.current[targetLineIndex];
      if (targetElement && fileAScrollRef.current) {
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } else {
      const targetLineIndex = match.file_b_start_line - 1;
      const targetElement = fileBLineRefs.current[targetLineIndex];
      if (targetElement && fileBScrollRef.current) {
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [selectedPair]);

  const sortedPairs = useMemo(() => {
    return [...pairs].sort((a, b) => {
      let valueA: any;
      let valueB: any;
      
      switch (sortField) {
        case 'file_a':
          valueA = a.file_a.filename.toLowerCase();
          valueB = b.file_b.filename.toLowerCase();
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

  const fileALines = useMemo(() => {
    if (!fileAContent || !selectedPair) return [];
    return parseFileContent(fileAContent.content, selectedPair.matches, true);
  }, [fileAContent, selectedPair]);

  const fileBLines = useMemo(() => {
    if (!fileBContent || !selectedPair) return [];
    return parseFileContent(fileBContent.content, selectedPair.matches, false);
  }, [fileBContent, selectedPair]);

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

        <Box flex={1} overflow="auto">
          <Card bg={bgColor}>
            <CardBody>
              <VStack align="stretch" spacing={6}>
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

                {loadingContent ? (
                  <Box textAlign="center" py={8}>
                    <Spinner size="lg" />
                    <Text mt={2}>Loading file contents...</Text>
                  </Box>
                ) : (
                  <>
                    <Flex gap={4}>
                      <FileViewer
                        lines={fileALines}
                        fileName={selectedPair.file_a.filename}
                        language={fileAContent?.language || 'unknown'}
                        hoveredMatchIndex={hoveredMatchIndex}
                        onHoverMatch={setHoveredMatchIndex}
                        onScrollToMatch={(idx) => handleScrollToMatch(idx, false)}
                        scrollRef={fileAScrollRef}
                        lineRefs={fileALineRefs}
                        isFileA={true}
                      />

                      <FileViewer
                        lines={fileBLines}
                        fileName={selectedPair.file_b.filename}
                        language={fileBContent?.language || 'unknown'}
                        hoveredMatchIndex={hoveredMatchIndex}
                        onHoverMatch={setHoveredMatchIndex}
                        onScrollToMatch={(idx) => handleScrollToMatch(idx, true)}
                        scrollRef={fileBScrollRef}
                        lineRefs={fileBLineRefs}
                        isFileA={false}
                      />
                    </Flex>

                    {selectedPair.matches && selectedPair.matches.length > 0 && (
                      <Card>
                        <CardBody>
                          <Heading size="sm" mb={4}>Matching Regions</Heading>
                          <VStack align="stretch" spacing={2}>
                            {selectedPair.matches.map((match, index) => {
                              const color = getMatchColor(index);
                              const isHovered = hoveredMatchIndex === index;
                              
                              return (
                                <Box
                                  key={index}
                                  p={3}
                                  borderRadius="md"
                                  borderLeftWidth={4}
                                  borderLeftColor={color.border}
                                  bg={isHovered ? color.hover : color.bg}
                                  onMouseEnter={() => setHoveredMatchIndex(index)}
                                  onMouseLeave={() => setHoveredMatchIndex(null)}
                                  cursor="pointer"
                                  transition="background-color 0.15s ease"
                                >
                                  <Flex gap={4} align="center">
                                    <Box flex={1}>
                                      <Text fontSize="xs" fontWeight="medium" color="gray.600">
                                        {selectedPair.file_a.filename}
                                      </Text>
                                      <Text fontSize="sm">
                                        Lines {match.file_a_start_line} - {match.file_a_end_line}
                                      </Text>
                                    </Box>
                                    <Box flex={1}>
                                      <Text fontSize="xs" fontWeight="medium" color="gray.600">
                                        {selectedPair.file_b.filename}
                                      </Text>
                                      <Text fontSize="sm">
                                        Lines {match.file_b_start_line} - {match.file_b_end_line}
                                      </Text>
                                    </Box>
                                    <Menu>
                                      <MenuButton
                                        as={Button}
                                        size="sm"
                                        variant="ghost"
                                        leftIcon={<FiCrosshair />}
                                      >
                                        Go to
                                      </MenuButton>
                                      <MenuList>
                                        <MenuItem onClick={() => handleScrollToMatch(index, true)}>
                                          Go to File 1 (Line {match.file_a_start_line})
                                        </MenuItem>
                                        <MenuItem onClick={() => handleScrollToMatch(index, false)}>
                                          Go to File 2 (Line {match.file_b_start_line})
                                        </MenuItem>
                                      </MenuList>
                                    </Menu>
                                  </Flex>
                                </Box>
                              );
                            })}
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
                      <Tr
                        key={pair.id}
                        _hover={{ bg: hoverBg, cursor: 'pointer' }}
                        onClick={() => handleCompare(pair)}
                      >
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
                        <Td isNumeric>
                          <Text fontSize="sm" color="gray.500">Click row to view</Text>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            </CardBody>
          </Card>
          
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