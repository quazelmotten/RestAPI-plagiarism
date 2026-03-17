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
  VStack,
  Text,
  Card,
  CardBody,
  useColorModeValue,
  Flex,
} from '@chakra-ui/react';
import { FiFolder } from 'react-icons/fi';
import api from '../services/api';
import FilePickerModal from '../components/FilePickerModal';
import { useSearchParams } from 'react-router';

interface FileInfo {
  id: string;
  filename: string;
  language: string;
}

interface FilePickerFile {
  id: string;
  filename: string;
  language: string;
  task_id: string;
  status: string;
  similarity?: number;
}

interface PlagiarismMatch {
  file_a_start_line: number;
  file_a_end_line: number;
  file_b_start_line: number;
  file_b_end_line: number;
}

// Matches are already in the correct format from the API
const transformMatches = (matches: any[]): PlagiarismMatch[] => {
  if (!Array.isArray(matches)) return [];
  return matches.map(m => ({
    file_a_start_line: m.file_a_start_line,
    file_a_end_line: m.file_a_end_line,
    file_b_start_line: m.file_b_start_line,
    file_b_end_line: m.file_b_end_line,
  }));
};

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

  const lineMatchMap = useMemo(() => {
    const map: Array<{ matchIndex: number } | null> = new Array(lines.length).fill(null);
    matches.forEach((match, index) => {
      const startLine = isFileA ? match.file_a_start_line : match.file_b_start_line;
      const endLine = isFileA ? match.file_a_end_line : match.file_b_end_line;
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
    const offsetInContainer = lineEl.offsetTop - container.scrollTop;
    onJumpToMatch(lineNumber, offsetInContainer, isFileA);
  }, [scrollContainerRef, onJumpToMatch, isFileA]);

  return (
    <Card flex={1} display="flex" flexDirection="column">
      <CardBody p={0} flex={1} display="flex" flexDirection="column">
        <Flex direction="column" h="100%">
          <HStack p={3} borderBottomWidth={1} borderColor={borderColor} justify="space-between">
            <Text fontWeight="bold">{fileName}</Text>
            <Badge colorScheme={isFileA ? 'blue' : 'green'}>{language || 'unknown'}</Badge>
          </HStack>
          <Box
            ref={scrollContainerRef}
            flex={1}
            overflowY="auto"
            overflowX="auto"
            fontFamily="monospace"
            fontSize="sm"
            minW={0}
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
                    : (matchInfo ? getMatchColor(matchInfo.matchIndex) : 'transparent')}
                  borderLeftWidth={matchInfo ? 4 : 0}
                  borderLeftColor={matchInfo ? getMatchBorder(matchInfo.matchIndex) : 'transparent'}
                  onMouseEnter={() => onHoverMatch(matchInfo ? matchInfo.matchIndex : null)}
                  onMouseLeave={() => onHoverMatch(null)}
                  onClick={(e) => matchInfo && handleClick(lineNumber, e)}
                  cursor={matchInfo ? 'pointer' : 'default'}
                  role={matchInfo ? 'button' : undefined}
                  tabIndex={matchInfo ? 0 : undefined}
                  minW="fit-content"
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
                     whiteSpace="pre-wrap"
                     wordBreak="break-word"
                     color={textColor}
                     minWidth={0}
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
  const [currentPair, setCurrentPair] = useState<PairResult | null>(null);
  const [selectedFileA, setSelectedFileA] = useState<FilePickerFile | null>(null);
  const [selectedFileB, setSelectedFileB] = useState<FilePickerFile | null>(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [contentError, setContentError] = useState<string | null>(null);
  const [hoveredMatchIndex, setHoveredMatchIndex] = useState<number | null>(null);
  const [analyzingMatches, setAnalyzingMatches] = useState(false);

  // Read URL query params for initial file selection
  const [searchParams] = useSearchParams();

  const fileAContainerRef = useRef<HTMLDivElement>(null);
  const fileBContainerRef = useRef<HTMLDivElement>(null);
  const fileALineRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const fileBLineRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const bgColor = useColorModeValue('white', 'gray.800');

  const currentPairMemo = useMemo(() => currentPair, [currentPair]);

  const isFileAInPair = useMemo(() => {
    if (!currentPairMemo) return false;
    return currentPairMemo.file_a.id === selectedFileA?.id;
  }, [currentPairMemo, selectedFileA?.id]);

  // Load file IDs from URL query params on mount
  useEffect(() => {
    const fileAId = searchParams.get('file_a');
    const fileBId = searchParams.get('file_b');
    if (fileAId && fileBId && !selectedFileA && !selectedFileB) {
      // Fetch files list to get full file objects
      api.get('/plagiarism/files/list')
        .then(res => {
          const fileA = res.data.find((f: any) => f.id === fileAId);
          const fileB = res.data.find((f: any) => f.id === fileBId);
          if (fileA && fileB) {
            setSelectedFileA(fileA);
            setSelectedFileB(fileB);
          }
        })
        .catch(err => {
          console.error('Failed to load files from URL params', err);
        });
    }
  }, [searchParams, selectedFileA, selectedFileB]);

  // Fetch specific file pair when selection changes
  useEffect(() => {
    if (selectedFileA && selectedFileB) {
      fetchFilePair();
    } else {
      setCurrentPair(null);
    }
  }, [selectedFileA, selectedFileB]);

   const fetchFilePair = async () => {
     if (!selectedFileA || !selectedFileB) return;
     try {
       const response = await api.get('/plagiarism/file-pair', {
         params: { file_a: selectedFileA.id, file_b: selectedFileB.id }
       });
       const pairData = response.data;

       // Transform matches from backend format to frontend format
       const transformedMatches = transformMatches(pairData.matches);
       pairData.matches = transformedMatches;

       // If matches are empty, trigger on-demand analysis
       if (!transformedMatches || transformedMatches.length === 0) {
         setAnalyzingMatches(true);
         try {
           const analyzeResponse = await api.post('/plagiarism/file-pair/analyze', null, {
             params: { file_a: selectedFileA.id, file_b: selectedFileB.id }
           });
          pairData.matches = transformMatches(analyzeResponse.data.matches);
          pairData.ast_similarity = analyzeResponse.data.ast_similarity;
        } catch (analyzeErr: any) {
          console.error('On-demand analysis failed:', analyzeErr);
        } finally {
          setAnalyzingMatches(false);
        }
      }

      setCurrentPair(pairData);
    } catch (err: any) {
      if (err.response?.status !== 404) {
        console.error('Error fetching file pair:', err);
      }
      setCurrentPair(null);
    }
  };

  const loadFileContent = useCallback(async () => {
    if (!selectedFileA || !selectedFileB) return;
    setLoadingContent(true);
    setFileAContent(null);
    setFileBContent(null);
    setContentError(null);
    fileALineRefs.current.clear();
    fileBLineRefs.current.clear();

    try {
      const [fileAResponse, fileBResponse] = await Promise.all([
        api.get(`/plagiarism/files/${selectedFileA.id}/content`),
        api.get(`/plagiarism/files/${selectedFileB.id}/content`)
      ]);
      setFileAContent(fileAResponse.data);
      setFileBContent(fileBResponse.data);
    } catch (error) {
      console.error('Error fetching file contents:', error);
      setContentError(error instanceof Error ? error.message : 'Failed to load file contents');
    } finally {
      setLoadingContent(false);
    }
  }, [selectedFileA, selectedFileB]);

  useEffect(() => {
    if (selectedFileA && selectedFileB) {
      loadFileContent();
    }
  }, [selectedFileA, selectedFileB, loadFileContent]);

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
    if (!currentPairMemo) return;
    let targetLine: number;
    let targetRefs: React.MutableRefObject<Map<number, HTMLDivElement>>;
    let targetContainer: HTMLDivElement | null;

    if (clickedIsFileA) {
      const match = currentPairMemo.matches.find(m =>
        clickedLine >= m.file_a_start_line && clickedLine <= m.file_a_end_line
      );
      if (!match) return;
      targetLine = match.file_b_start_line + (clickedLine - match.file_a_start_line);
      targetRefs = fileBLineRefs;
      targetContainer = fileBContainerRef.current;
    } else {
      const match = currentPairMemo.matches.find(m =>
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
    const targetOffset = targetEl.offsetTop;
    const newScrollTop = targetOffset - clickedLineOffset;
    const maxScrollTop = targetContainer.scrollHeight - targetContainer.clientHeight;
    targetContainer.scrollTop = Math.max(0, Math.min(newScrollTop, maxScrollTop));
  }, [currentPairMemo]);

  return (
    <Box minH="100vh" display="flex" flexDir="column">

      <Card mb={4} bg={bgColor}>
        <CardBody>
          <VStack spacing={4}>
            <HStack spacing={4} w="100%" justify="center">
              <Button
                leftIcon={<FiFolder />}
                size="lg"
                variant="outline"
                flex={1}
                onClick={() => setIsPickerOpen(true)}
                title="Select files to compare"
              >
                {selectedFileA && selectedFileB
                  ? `${selectedFileA.filename} vs ${selectedFileB.filename}`
                  : 'Select Files to Compare'}
              </Button>
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
            </HStack>

            <Text fontSize="sm" color="gray.600" textAlign="center">
              Click any highlighted region to jump to the matching region in the other file
            </Text>

            {analyzingMatches && (
              <HStack justify="center">
                <Spinner size="sm" />
                <Text fontSize="sm" color="blue.500">Computing match details...</Text>
              </HStack>
            )}

            {contentError && (
              <Alert status="warning">
                <AlertIcon />
                {contentError}
              </Alert>
            )}
          </VStack>
        </CardBody>
      </Card>

      {loadingContent ? (
        <Box flex={1} display="flex" alignItems="center" justifyContent="center" py={8}>
          <Spinner size="lg" />
          <Text mt={2}>Loading file contents...</Text>
        </Box>
      ) : (
        <Flex flex={1} gap={4} align="stretch" py={4} px={2}>
          <FileViewer
            content={fileAContent?.content || ''}
            fileName={fileAContent?.filename || 'File A'}
            language={fileAContent?.language || 'unknown'}
            matches={currentPair?.matches || []}
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
            matches={currentPair?.matches || []}
            isFileA={!isFileAInPair}
            hoveredMatchIndex={hoveredMatchIndex}
            onHoverMatch={setHoveredMatchIndex}
            onJumpToMatch={handleJumpToMatch}
            scrollContainerRef={fileBContainerRef}
            getLineRef={getLineRef(false)}
          />
         </Flex>
       )}

       <FilePickerModal
         isOpen={isPickerOpen}
         onClose={() => setIsPickerOpen(false)}
         onSelect={(fileA, fileB) => {
           setSelectedFileA(fileA);
           setSelectedFileB(fileB);
           setHoveredMatchIndex(null);
           fileALineRefs.current.clear();
           fileBLineRefs.current.clear();
         }}
         initialFileAId={selectedFileA?.id}
         initialFileBId={selectedFileB?.id}
       />
     </Box>
   );
 };

export default PairComparison;
