import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Box,
  Spinner,
  Text,
  useColorModeValue,
  Flex,
} from '@chakra-ui/react';
import api, { API_ENDPOINTS } from '../services/api';
import FilePickerModal from '../components/FilePickerModal';
import { useSearchParams } from 'react-router';
import type { FileInfo, FileContent, PlagiarismResult as ApiPlagiarismResult, PlagiarismMatch as ApiPlagiarismMatch, ApiError } from '../types';
import ErrorBoundary from '../components/ErrorBoundary';

// FilePickerFile is now FileInfo from types
type FilePickerFile = FileInfo;

type PlagiarismMatch = ApiPlagiarismMatch;

// Matches are already in the correct format from the API
const transformMatches = (matches: ApiPlagiarismMatch[]): PlagiarismMatch[] => {
  if (!Array.isArray(matches)) return [];
  return matches.map(m => ({
    file_a_start_line: m.file_a_start_line,
    file_a_end_line: m.file_a_end_line,
    file_b_start_line: m.file_b_start_line,
    file_b_end_line: m.file_b_end_line,
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
       api.get<FileInfo[]>(API_ENDPOINTS.FILES_LIST)
         .then(res => {
           const fileA = res.data.find((f) => f.id === fileAId);
           const fileB = res.data.find((f) => f.id === fileBId);
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

       // Transform matches from backend format to frontend format
       const transformedMatches = transformMatches(pairData.matches);
       pairData.matches = transformedMatches;

       // If matches are empty, trigger on-demand analysis
       if (!transformedMatches || transformedMatches.length === 0) {
         setAnalyzingMatches(true);
         try {
           const analyzeResponse = await api.post<{ matches: ApiPlagiarismMatch[]; ast_similarity: number }>(API_ENDPOINTS.FILE_PAIR_ANALYZE, null, {
             params: { file_a: selectedFileA.id, file_b: selectedFileB.id }
           });
          pairData.matches = transformMatches(analyzeResponse.data.matches);
          pairData.ast_similarity = analyzeResponse.data.ast_similarity;
        } catch (analyzeErr: unknown) {
          console.error('On-demand analysis failed:', analyzeErr);
        } finally {
          setAnalyzingMatches(false);
        }
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

      {loadingContent ? (
        <Box flex={1} display="flex" alignItems="center" justifyContent="center" py={8}>
          <Spinner size="lg" />
          <Text mt={2}>Loading file contents...</Text>
        </Box>
       ) : (
         <ErrorBoundary>
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
