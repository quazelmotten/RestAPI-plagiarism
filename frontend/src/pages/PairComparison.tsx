import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Box,
  Spinner,
  Text,
  useColorModeValue,
  Flex,
  IconButton,
  HStack,
  Tooltip,
} from '@chakra-ui/react';
import { FiEye, FiEyeOff, FiChevronUp, FiChevronDown } from 'react-icons/fi';
import api, { API_ENDPOINTS } from '../services/api';
import FilePickerModal from '../components/FilePickerModal';
import { useSearchParams } from 'react-router';
import type { FileInfo, FileContent, PlagiarismResult as ApiPlagiarismResult, PlagiarismMatch as ApiPlagiarismMatch, ApiError } from '../types';
import ErrorBoundary from '../components/ErrorBoundary';

// FilePickerFile is now FileInfo from types
type FilePickerFile = FileInfo;

type PlagiarismMatch = ApiPlagiarismMatch;

// Backend returns { file1: {start_line, end_line, ...}, file2: {start_line, end_line, ...}, kgram_count, plagiarism_type, ... }
// Frontend expects { file_a_start_line, file_a_end_line, file_b_start_line, file_b_end_line, ... }
const transformMatches = (matches: any[]): PlagiarismMatch[] => {
  if (!Array.isArray(matches)) return [];
  return matches.map(m => ({
    file_a_start_line: m.file1?.start_line ?? m.file_a_start_line,
    file_a_end_line: m.file1?.end_line ?? m.file_a_end_line,
    file_b_start_line: m.file2?.start_line ?? m.file_b_start_line,
    file_b_end_line: m.file2?.end_line ?? m.file_b_end_line,
    plagiarism_type: m.plagiarism_type ?? m.plagiarism_type ?? 1,
    similarity: m.similarity ?? 1.0,
    details: m.details ?? null,
    description: m.description ?? null,
  }));
};

type PairResult = ApiPlagiarismResult & {
  task_id?: string;
};

import FileViewer from '../components/PairComparison/FileViewer';
import ComparisonHeader from '../components/PairComparison/ComparisonHeader';

const getSimilarityGradient = (similarity: number): string => {
  if (similarity >= 0.8) return 'linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%)';
  if (similarity >= 0.5) return 'linear-gradient(135deg, #ffa726 0%, #fb8c00 100%)';
  if (similarity >= 0.3) return 'linear-gradient(135deg, #ffca28 0%, #ffb300 100%)';
  return 'linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)';
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
  const [filterComments, setFilterComments] = useState(false);
  const [headerVisible, setHeaderVisible] = useState(true);

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
    return currentPairMemo.file_a.id === (selectedFileA ? selectedFileA.id : undefined);
  }, [currentPairMemo, selectedFileA]);

   // Load file IDs from URL query params on mount
   useEffect(() => {
     const fileAId = searchParams.get('file_a');
     const fileBId = searchParams.get('file_b');
     if (fileAId && fileBId && !selectedFileA && !selectedFileB) {
       // Fetch files list to get full file objects
        api.get<{ items: FileInfo[] }>(API_ENDPOINTS.FILES_LIST)
          .then(res => {
            const fileA = res.data.items.find((f) => f.id === fileAId);
            const fileB = res.data.items.find((f) => f.id === fileBId);
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

    const fetchFilePair = useCallback(async () => {
      if (!selectedFileA || !selectedFileB) return;
      try {
        const response = await api.get<ApiPlagiarismResult>(API_ENDPOINTS.FILE_PAIR, {
          params: { file_a: selectedFileA.id, file_b: selectedFileB.id }
        });
        const pairData = response.data;

        // Always run on-demand analysis for fresh, correctly-merged matches.
        // DB stores only similarity scores (worker doesn't compute match details).
        setAnalyzingMatches(true);
        try {
          const analyzeResponse = await api.post<{ matches: ApiPlagiarismMatch[]; ast_similarity: number }>(API_ENDPOINTS.FILE_PAIR_ANALYZE, null, {
            params: { file_a: selectedFileA.id, file_b: selectedFileB.id }
          });
          pairData.matches = transformMatches(analyzeResponse.data.matches);
          pairData.ast_similarity = analyzeResponse.data.ast_similarity;
        } catch (analyzeErr: unknown) {
          console.error('On-demand analysis failed:', analyzeErr);
          // Fall back to whatever the DB had
          pairData.matches = transformMatches(pairData.matches);
        } finally {
          setAnalyzingMatches(false);
        }

        setCurrentPair(pairData);
      } catch (err: unknown) {
        const error = err as ApiError;
        if (error.response?.status !== 404) {
          console.error('Error fetching file pair:', err);
        }
        setCurrentPair(null);
      }
      }, [selectedFileA, selectedFileB]);

  useEffect(() => {
    if (selectedFileA && selectedFileB) {
      fetchFilePair();
    } else {
      setCurrentPair(null);
    }
  }, [selectedFileA, selectedFileB, fetchFilePair]);

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
        api.get<FileContent>(API_ENDPOINTS.FILE_CONTENT(selectedFileA.id)),
        api.get<FileContent>(API_ENDPOINTS.FILE_CONTENT(selectedFileB.id))
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

  const handleJumpToMatch = useCallback((clickedLine: number, targetViewportOffset: number, clickedIsFileA: boolean) => {
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

    // Use getBoundingClientRect for reliable positioning regardless of CSS intermediaries
    const targetRect = targetEl.getBoundingClientRect();
    const containerRect = targetContainer.getBoundingClientRect();
    const containerBorderTop = parseFloat(getComputedStyle(targetContainer).borderTopWidth) || 0;
    const targetCurrentOffset = targetRect.top - containerRect.top - containerBorderTop;
    const scrollDelta = targetCurrentOffset - targetViewportOffset;
    const newScrollTop = targetContainer.scrollTop + scrollDelta;

    targetContainer.scrollTo({ top: newScrollTop, behavior: 'smooth' });
  }, [currentPairMemo]);

  return (
    <Box h="100vh" display="flex" flexDir="column" overflow="hidden">
      {headerVisible ? (
        <ComparisonHeader
          selectedFileA={selectedFileA}
          selectedFileB={selectedFileB}
          currentPair={currentPair}
          getSimilarityGradient={getSimilarityGradient}
          onOpenPicker={() => setIsPickerOpen(true)}
          analyzingMatches={analyzingMatches}
          contentError={contentError}
          bgColor={bgColor}
        />
      ) : (
        <HStack px={2} py={1} flexShrink={0}>
          <Tooltip label="Show header" placement="bottom">
            <IconButton
              aria-label="Show header"
              icon={<FiChevronDown />}
              size="sm"
              variant="ghost"
              onClick={() => setHeaderVisible(true)}
            />
          </Tooltip>
          {currentPair && (
            <Text fontSize="sm" fontWeight="bold" ml={2}>
              {((currentPair.ast_similarity || 0) * 100).toFixed(1)}% similarity
            </Text>
          )}
        </HStack>
      )}

      <HStack px={2} py={1} flexShrink={0} spacing={1}>
        <Tooltip label={filterComments ? 'Show comments' : 'Hide comments'} placement="bottom">
          <IconButton
            aria-label={filterComments ? 'Show comments' : 'Hide comments'}
            icon={filterComments ? <FiEye /> : <FiEyeOff />}
            size="sm"
            variant={filterComments ? 'solid' : 'ghost'}
            colorScheme={filterComments ? 'orange' : 'gray'}
            onClick={() => setFilterComments(!filterComments)}
          />
        </Tooltip>
        {headerVisible && (
          <Tooltip label="Hide header" placement="bottom">
            <IconButton
              aria-label="Hide header"
              icon={<FiChevronUp />}
              size="sm"
              variant="ghost"
              onClick={() => setHeaderVisible(false)}
            />
          </Tooltip>
        )}
      </HStack>

      {loadingContent ? (
        <Box flex={1} display="flex" alignItems="center" justifyContent="center" py={8} minH={0}>
          <Spinner size="lg" />
          <Text mt={2}>Loading file contents...</Text>
        </Box>
       ) : (
         <ErrorBoundary>
           <Flex flex={1} gap={4} align="stretch" py={4} px={2} minH={0} overflow="hidden">
              <FileViewer
                content={fileAContent?.content || ''}
                fileName={fileAContent?.filename || 'File A'}
                language={fileAContent?.language || 'unknown'}
                matches={currentPair?.matches || []}
                isFileA={isFileAInPair}
                filterComments={filterComments}
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
                filterComments={filterComments}
                hoveredMatchIndex={hoveredMatchIndex}
                onHoverMatch={setHoveredMatchIndex}
                onJumpToMatch={handleJumpToMatch}
                scrollContainerRef={fileBContainerRef}
                getLineRef={getLineRef(false)}
              />
           </Flex>
         </ErrorBoundary>
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
  }

export default PairComparison;
