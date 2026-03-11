import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Box,
  Heading,
  Badge,
  Button,
  Spinner,
  Alert,
  AlertIcon,
  HStack,
  Text,
  Card,
  CardBody,
  useColorModeValue,
  Flex,
  Select,
} from '@chakra-ui/react';
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

const MATCH_COLORS = [
  'rgba(255, 235, 59, 0.3)',
  'rgba(76, 175, 80, 0.25)',
  'rgba(33, 150, 243, 0.25)',
  'rgba(156, 39, 176, 0.25)',
  'rgba(255, 87, 34, 0.25)',
  'rgba(0, 188, 212, 0.25)',
  'rgba(233, 30, 99, 0.25)',
  'rgba(255, 152, 0, 0.25)',
];

const MATCH_COLORS_HOVER = [
  'rgba(255, 235, 59, 0.7)',
  'rgba(76, 175, 80, 0.6)',
  'rgba(33, 150, 243, 0.6)',
  'rgba(156, 39, 176, 0.6)',
  'rgba(255, 87, 34, 0.6)',
  'rgba(0, 188, 212, 0.6)',
  'rgba(233, 30, 99, 0.6)',
  'rgba(255, 152, 0, 0.6)',
];

const MATCH_BORDERS = [
  '#FBC02D',
  '#388E3C',
  '#1976D2',
  '#7B1FA2',
  '#E64A19',
  '#0097A7',
  '#C2185B',
  '#F57C00',
];

const getMatchColor = (matchIndex: number) => MATCH_COLORS[matchIndex % MATCH_COLORS.length];
const getMatchColorHover = (matchIndex: number) => MATCH_COLORS_HOVER[matchIndex % MATCH_COLORS_HOVER.length];
const getMatchBorder = (matchIndex: number) => MATCH_BORDERS[matchIndex % MATCH_BORDERS.length];

const getSimilarityGradient = (similarity: number): string => {
  if (similarity >= 0.8) return 'linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%)';
  if (similarity >= 0.5) return 'linear-gradient(135deg, #ffa726 0%, #fb8c00 100%)';
  if (similarity >= 0.3) return 'linear-gradient(135deg, #ffca28 0%, #ffb300 100%)';
  return 'linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)';
};

interface FileViewerProps {
  content: string;
  fileName: string;
  language: string;
  matches: PlagiarismMatch[];
  isFileA: boolean;
  hoveredMatchIndex: number | null;
  onHoverMatch: (index: number | null) => void;
  onJumpToMatch: (clickedLine: number, clickedLineOffset: number, clickedIsFileA: boolean) => void;
  scrollContainerRef: React.RefObject<HTMLDivElement | null>;
  getLineRef: (lineIndex: number, el: HTMLDivElement | null) => void;
}

const FileViewer: React.FC<FileViewerProps> = ({
  content,
  fileName,
  language,
  matches,
  isFileA,
  hoveredMatchIndex,
  onHoverMatch,
  onJumpToMatch,
  scrollContainerRef,
  getLineRef,
}) => {
  const lineNumberBg = useColorModeValue('gray.100', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const lineNumberColor = useColorModeValue('gray.500', 'gray.400');

  const lines = useMemo(() => content.split('\n'), [content]);

  // Precompute line-to-match mapping for O(1) lookup
  const lineMatchMap = useMemo(() => {
    const map: Array<{ matchIndex: number } | null> = new Array(lines.length).fill(null);
    matches.forEach((match, index) => {
      const startLine = isFileA ? match.file_a_start_line : match.file_b_start_line;
      const endLine = isFileA ? match.file_a_end_line : match.file_b_end_line;
      
      // Convert 1-based to 0-based array indices
      for (let lineNum = Math.max(1, startLine); lineNum <= endLine && lineNum <= lines.length; lineNum++) {
        const idx = lineNum - 1;
        if (map[idx] === null) {
          map[idx] = { matchIndex: index };
        }
      }
    });
    return map;
  }, [lines.length, matches, isFileA]);

  const handleClick = useCallback((lineNumber: number, event: React.MouseEvent) => {
    const lineEl = event.currentTarget as HTMLDivElement;
    const container = scrollContainerRef.current;
    if (!container) return;
    
    // offsetTop is relative to offsetParent (container's padding box)
    const offsetInContainer = lineEl.offsetTop - container.scrollTop;
    onJumpToMatch(lineNumber, offsetInContainer, isFileA);
  }, [scrollContainerRef, onJumpToMatch, isFileA]);

  return (
    <Card flex={1}>
      <CardBody p={0}>
        <Flex direction="column" h="100%">
          <HStack p={3} borderBottomWidth={1} borderColor={borderColor} justify="space-between">
            <Text fontWeight="bold">{fileName}</Text>
            <Badge colorScheme={isFileA ? 'blue' : 'green'}>{language || 'unknown'}</Badge>
          </HStack>
          <Box
            ref={scrollContainerRef}
            flex={1}
            overflowY="auto"
            fontFamily="monospace"
            fontSize="sm"
            maxH="calc(100vh - 20rem)" // More responsive than 320px
          >
            {lines.map((line, idx) => {
              const lineNumber = idx + 1;
              const matchInfo = lineMatchMap[idx];
              const isHovered = matchInfo !== null && matchInfo.matchIndex === hoveredMatchIndex;
              
              return (
                <Flex
                  key={idx}
                  ref={(el) => getLineRef(idx, el)}
                  bg={isHovered 
                    ? getMatchColorHover(matchInfo!.matchIndex) 
                    : (matchInfo ? getMatchColor(matchInfo.matchIndex) : 'transparent')
                  }
                  borderLeftWidth={matchInfo ? 4 : 0}
                  borderLeftColor={matchInfo ? getMatchBorder(matchInfo.matchIndex) : 'transparent'}
                  onMouseEnter={() => onHoverMatch(matchInfo ? matchInfo.matchIndex : null)}
                  onMouseLeave={() => onHoverMatch(null)}
                  onClick={(e) => matchInfo && handleClick(lineNumber, e)}
                  cursor={matchInfo ? 'pointer' : 'default'}
                  role={matchInfo ? 'button' : undefined}
                  tabIndex={matchInfo ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (matchInfo && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      handleClick(lineNumber, e as any);
                    }
                  }}
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
                    {lineNumber}
                  </Box>
                  <Box
                    flex={1}
                    pl={3}
                    py={0.5}
                    whiteSpace="pre"
                    overflow="hidden"
                    color={textColor}
                  >
                    {line || ' '}
                  </Box>
                </Flex>
              );
            })}
          </Box>
        </Flex>
      </CardBody>
    </Card>
  );
};

const PairComparison: React.FC = () => {
  const [pairs, setPairs] = useState<PairResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFileAId, setSelectedFileAId] = useState<string>('');
  const [selectedFileBId, setSelectedFileBId] = useState<string>('');
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [contentError, setContentError] = useState<string | null>(null);
  const [hoveredMatchIndex, setHoveredMatchIndex] = useState<number | null>(null);

  const fileAContainerRef = useRef<HTMLDivElement>(null);
  const fileBContainerRef = useRef<HTMLDivElement>(null);
  const fileALineRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const fileBLineRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const bgColor = useColorModeValue('white', 'gray.800');

  const uniqueFiles = useMemo(() => {
    const fileMap = new Map<string, { id: string; filename: string }>();
    pairs.forEach(pair => {
      fileMap.set(pair.file_a.id, pair.file_a);
      fileMap.set(pair.file_b.id, pair.file_b);
    });
    return Array.from(fileMap.values());
  }, [pairs]);

  const currentPair = useMemo(() => {
    return pairs.find(p => 
      (p.file_a.id === selectedFileAId && p.file_b.id === selectedFileBId) ||
      (p.file_a.id === selectedFileBId && p.file_b.id === selectedFileAId)
    ) || null;
  }, [pairs, selectedFileAId, selectedFileBId]);

  // Determine which selected file corresponds to pair.file_a
  const isFileAInPair = useMemo(() => {
    if (!currentPair) return false;
    return currentPair.file_a.id === selectedFileAId;
  }, [currentPair, selectedFileAId]);

  // Memoize matches for FileViewer to prevent unnecessary re-renders
  const memoizedMatches = useMemo(() => currentPair?.matches || [], [currentPair]);

  useEffect(() => {
    fetchAllPairs();
  }, []);

  useEffect(() => {
    if (selectedFileAId && selectedFileBId) {
      loadFileContent();
    }
  }, [selectedFileAId, selectedFileBId]);

  const fetchAllPairs = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get('/plagiarism/results/all');

      if (!Array.isArray(response.data)) {
        setError('Invalid data format received from server');
        setPairs([]);
        return;
      }

      setPairs(response.data || []);
      
      if (response.data && response.data.length > 0) {
        const firstPair = response.data[0];
        setSelectedFileAId(firstPair.file_a.id);
        setSelectedFileBId(firstPair.file_b.id);
      }
    } catch (err) {
      console.error('Error fetching pairs:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch pairs';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const loadFileContent = useCallback(async () => {
    if (!selectedFileAId || !selectedFileBId) return;
    
    setLoadingContent(true);
    setFileAContent(null);
    setFileBContent(null);
    setContentError(null);
    fileALineRefs.current.clear();
    fileBLineRefs.current.clear();

    try {
      const [fileAResponse, fileBResponse] = await Promise.all([
        api.get(`/plagiarism/files/${selectedFileAId}/content`),
        api.get(`/plagiarism/files/${selectedFileBId}/content`)
      ]);

      setFileAContent(fileAResponse.data);
      setFileBContent(fileBResponse.data);
    } catch (error) {
      console.error('Error fetching file contents:', error);
      setContentError(error instanceof Error ? error.message : 'Failed to load file contents');
    } finally {
      setLoadingContent(false);
    }
  }, [selectedFileAId, selectedFileBId]);

  const getLineRef = useCallback((fileA: boolean) => (lineIndex: number, el: HTMLDivElement | null) => {
    if (el) {
      if (fileA) {
        fileALineRefs.current.set(lineIndex, el);
      } else {
        fileBLineRefs.current.set(lineIndex, el);
      }
    }
  }, []);

  const handleJumpToMatch = useCallback((clickedLine: number, clickedLineOffset: number, clickedIsFileA: boolean) => {
    if (!currentPair) return;
    
    let targetLine: number;
    let targetRefs: React.MutableRefObject<Map<number, HTMLDivElement>>;
    let targetContainer: HTMLDivElement | null;
    
    if (clickedIsFileA) {
      const match = currentPair.matches.find(m => 
        clickedLine >= m.file_a_start_line && clickedLine <= m.file_a_end_line
      );
      if (!match) return;
      targetLine = match.file_b_start_line + (clickedLine - match.file_a_start_line);
      targetRefs = fileBLineRefs;
      targetContainer = fileBContainerRef.current;
    } else {
      const match = currentPair.matches.find(m => 
        clickedLine >= m.file_b_start_line && clickedLine <= m.file_b_end_line
      );
      if (!match) return;
      targetLine = match.file_a_start_line + (clickedLine - match.file_b_start_line);
      targetRefs = fileALineRefs;
      targetContainer = fileAContainerRef.current;
    }

    if (!targetContainer) return;
    
    const targetEl = targetRefs.current.get(targetLine - 1);
    if (!targetEl) return;

    // Calculate target offset relative to its container
    const targetOffset = targetEl.offsetTop;
    
    // Set scroll so target line appears at same offset as clicked line
    const newScrollTop = targetOffset - clickedLineOffset;
    const maxScrollTop = targetContainer.scrollHeight - targetContainer.clientHeight;
    targetContainer.scrollTop = Math.max(0, Math.min(newScrollTop, maxScrollTop));
  }, [currentPair]);

  const handleFileAChange = (fileId: string) => {
    setSelectedFileAId(fileId);
    setHoveredMatchIndex(null);
    fileALineRefs.current.clear();
    fileBLineRefs.current.clear();
  };

  const handleFileBChange = (fileId: string) => {
    setSelectedFileBId(fileId);
    setHoveredMatchIndex(null);
    fileALineRefs.current.clear();
    fileBLineRefs.current.clear();
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

  if (pairs.length === 0) {
    return (
      <Box>
        <Heading mb={6}>Pair Comparison</Heading>
        <Card>
          <CardBody>
            <Text textAlign="center" color="gray.500" py={8}>
              No plagiarism comparisons found. Upload files and run plagiarism checks to see pairs.
            </Text>
          </CardBody>
        </Card>
      </Box>
    );
  }

  return (
    <Box>
      <Heading mb={4}>Pair Comparison</Heading>

      <Card mb={4} bg={bgColor}>
        <CardBody>
          <Flex align="center" gap={4} mb={3}>
            <Select
              value={selectedFileAId}
              onChange={(e) => handleFileAChange(e.target.value)}
              flex={1}
              size="lg"
            >
              {uniqueFiles.map((file) => (
                <option key={file.id} value={file.id}>
                  {file.filename}
                </option>
              ))}
            </Select>
            <Text fontSize="lg" fontWeight="bold">vs</Text>
            <Select
              value={selectedFileBId}
              onChange={(e) => handleFileBChange(e.target.value)}
              flex={1}
              size="lg"
            >
              {uniqueFiles.map((file) => (
                <option key={file.id} value={file.id}>
                  {file.filename}
                </option>
              ))}
            </Select>
            {currentPair && (
              <Box
                px={6}
                py={3}
                borderRadius="lg"
                bg={getSimilarityGradient(currentPair.ast_similarity || 0)}
                color="white"
                textAlign="center"
                minW="120px"
              >
                <Text fontSize="xl" fontWeight="bold">
                  {((currentPair.ast_similarity || 0) * 100).toFixed(1)}%
                </Text>
              </Box>
            )}
          </Flex>
          <Text fontSize="sm" color="gray.600" textAlign="center">
            Click any highlighted region to jump to the matching region in the other file
          </Text>
          {contentError && (
            <Alert status="warning" mt={2}>
              <AlertIcon />
              {contentError}
            </Alert>
          )}
        </CardBody>
      </Card>

      {loadingContent ? (
        <Box textAlign="center" py={8}>
          <Spinner size="lg" />
          <Text mt={2}>Loading file contents...</Text>
        </Box>
      ) : (
        <Flex gap={4} align="stretch">
          <FileViewer
            content={fileAContent?.content || ''}
            fileName={fileAContent?.filename || 'File A'}
            language={fileAContent?.language || 'unknown'}
            matches={memoizedMatches}
            isFileA={isFileAInPair}
            hoveredMatchIndex={hoveredMatchIndex}
            onHoverMatch={setHoveredMatchIndex}
            onJumpToMatch={handleJumpToMatch}
            scrollContainerRef={fileAContainerRef}
            getLineRef={getLineRef(true)}
          />

          <FileViewer
            content={fileBContent?.content || ''}
            fileName={fileBContent?.filename || 'File B'}
            language={fileBContent?.language || 'unknown'}
            matches={memoizedMatches}
            isFileA={!isFileAInPair}
            hoveredMatchIndex={hoveredMatchIndex}
            onHoverMatch={setHoveredMatchIndex}
            onJumpToMatch={handleJumpToMatch}
            scrollContainerRef={fileBContainerRef}
            getLineRef={getLineRef(false)}
          />
        </Flex>
      )}
    </Box>
  );
};

export default PairComparison;