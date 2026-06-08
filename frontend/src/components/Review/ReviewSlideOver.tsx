import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Box,
  Flex,
  HStack,
  Text,
  IconButton,
  Tooltip,
  Badge,
  Button,
  Spinner,
  useColorModeValue,
  Drawer,
  DrawerOverlay,
  DrawerContent,
  DrawerHeader,
  DrawerBody,
  DrawerFooter,
  DrawerCloseButton,
  useToast,
} from '@chakra-ui/react';
import {
  FiChevronLeft,
  FiChevronRight,
  FiCheck,
  FiX,
  FiEye,
  FiEyeOff,
  FiLink,
  FiLink2,
  FiCode,
  FiFilter,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../../services/api';
import FileViewer from '../PairComparison/FileViewer';
import type {
  FileInfo,
  FileContent,
  PlagiarismResult as ApiPlagiarismResult,
  PlagiarismMatch as ApiPlagiarismMatch,
  ApiError,
  ReviewPair,
} from '../../types';
import { MINIMAP_PALETTE } from '../../types';

type PlagiarismMatch = ApiPlagiarismMatch;

const isCommentLine = (line: string, language: string): boolean => {
  const trimmed = line.trim();
  if (!trimmed) return false;

  if (['python', 'ruby', 'perl', 'bash', 'shell'].includes(language)) {
    return trimmed.startsWith('#');
  }

  if (['javascript', 'typescript', 'tsx', 'c', 'cpp', 'java', 'go', 'rust', 'kotlin', 'swift', 'csharp'].includes(language)) {
    return trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*') || trimmed.startsWith('*/');
  }

  if (['sql', 'lua'].includes(language)) {
    return trimmed.startsWith('--');
  }

  if (language === 'html' || language === 'xml') {
    return trimmed.startsWith('<!--') || trimmed.endsWith('-->');
  }

  if (['css', 'scss', 'less'].includes(language)) {
    return trimmed.startsWith('/*') || trimmed.startsWith('*') || trimmed.startsWith('*/');
  }

  return false;
};

interface BackendMatch {
  file1?: { start_line: number; end_line: number };
  file2?: { start_line: number; end_line: number };
  file_a_start_line?: number;
  file_a_end_line?: number;
  file_b_start_line?: number;
  file_b_end_line?: number;
  plagiarism_type?: number;
  similarity?: number;
  details?: Record<string, unknown> | null;
  description?: string | null;
}

const transformMatches = (matches: BackendMatch[]): PlagiarismMatch[] => {
  if (!Array.isArray(matches)) return [];
  return matches.map(m => ({
    file_a_start_line: m.file1?.start_line ?? m.file_a_start_line ?? 0,
    file_a_end_line: m.file1?.end_line ?? m.file_a_end_line ?? 0,
    file_b_start_line: m.file2?.start_line ?? m.file_b_start_line ?? 0,
    file_b_end_line: m.file2?.end_line ?? m.file_b_end_line ?? 0,
    plagiarism_type: m.plagiarism_type ?? 1,
    similarity: m.similarity ?? 1.0,
    details: m.details ?? null,
    description: m.description ?? null,
  }));
};

interface ReviewSlideOverProps {
  isOpen: boolean;
  onClose: () => void;
  pairs: ReviewPair[];
  initialIndex?: number;
  onActionComplete?: (action: 'confirm' | 'clear', pairId: string) => void;
  onNavigate?: (direction: 'next' | 'prev') => void;
}

const getSimilarityColor = (sim: number): string => {
  if (sim >= 0.8) return 'red';
  if (sim >= 0.5) return 'orange';
  if (sim >= 0.3) return 'yellow';
  return 'green';
};

const ReviewSlideOver: React.FC<ReviewSlideOverProps> = ({
  isOpen,
  onClose,
  pairs,
  initialIndex = 0,
  onActionComplete,
  onNavigate,
}) => {
  const { t } = useTranslation(['pairComparison', 'common']);
  const toast = useToast();

  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [currentPair, setCurrentPair] = useState<ApiPlagiarismResult | null>(null);
  const [selectedFileA, setSelectedFileA] = useState<FileInfo | null>(null);
  const [selectedFileB, setSelectedFileB] = useState<FileInfo | null>(null);
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [contentError, setContentError] = useState<string | null>(null);
  const [hoveredMatchIndex, setHoveredMatchIndex] = useState<number | null>(null);
  const [analyzingMatches, setAnalyzingMatches] = useState(false);
  const [filterComments, setFilterComments] = useState(false);
  const [filterEmpty, setFilterEmpty] = useState(false);
  const [syntaxHighlight, setSyntaxHighlight] = useState(false);
  const [syncScroll, setSyncScroll] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [clearing, setClearing] = useState(false);

  const scrollSyncing = useRef(false);
  const resultIdRef = useRef<string | null>(null);

  const headerBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const minimapBg = useColorModeValue('gray.100', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const fileAContainerRef = useRef<HTMLDivElement>(null);
  const fileBContainerRef = useRef<HTMLDivElement>(null);
  const fileALineRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const fileBLineRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Initialize from props when opening
  useEffect(() => {
    if (isOpen && pairs.length > 0) {
      const idx = Math.min(initialIndex, pairs.length - 1);
      setCurrentIndex(idx);
      const pair = pairs[idx];
      setSelectedFileA({ id: pair.file_a_id, filename: pair.file_a_name, language: '', task_id: pair.task_id, status: '', similarity: undefined });
      setSelectedFileB({ id: pair.file_b_id, filename: pair.file_b_name, language: '', task_id: pair.task_id, status: '', similarity: undefined });
      setCurrentPair(null);
      setFileAContent(null);
      setFileBContent(null);
      resultIdRef.current = null;
    }
  }, [isOpen, pairs, initialIndex]);

  // Keep resultIdRef in sync
  useEffect(() => {
    resultIdRef.current = currentPair?.id || null;
  }, [currentPair]);

  // Match statistics
  const matchStats = useMemo(() => {
    const matches = currentPair?.matches || [];

    const computeEffectiveLines = (content: string, lang: string): Set<number> => {
      const lines = content.split('\n');
      const set = new Set<number>();
      lines.forEach((line, idx) => {
        const trimmed = line.trim();
        if (trimmed === '') return;
        if (isCommentLine(line, lang)) return;
        set.add(idx);
      });
      return set;
    };

    const contentA = fileAContent?.content || '';
    const langA = fileAContent?.language || '';
    const effectiveA = contentA ? computeEffectiveLines(contentA, langA) : new Set<number>();
    const totalEffectiveA = effectiveA.size;

    const contentB = fileBContent?.content || '';
    const langB = fileBContent?.language || '';
    const effectiveB = contentB ? computeEffectiveLines(contentB, langB) : new Set<number>();
    const totalEffectiveB = effectiveB.size;

    const coveredA = new Set<number>();
    const coveredB = new Set<number>();

    for (const m of matches) {
      for (let i = m.file_a_start_line - 1; i <= m.file_a_end_line - 1; i++) {
        if (effectiveA.has(i)) coveredA.add(i);
      }
      for (let i = m.file_b_start_line - 1; i <= m.file_b_end_line - 1; i++) {
        if (effectiveB.has(i)) coveredB.add(i);
      }
    }

    return {
      totalMatches: matches.length,
      coverageA: totalEffectiveA > 0 ? (coveredA.size / totalEffectiveA) * 100 : 0,
      coverageB: totalEffectiveB > 0 ? (coveredB.size / totalEffectiveB) * 100 : 0,
    };
  }, [currentPair, fileAContent, fileBContent]);

  // Minimap data
  const minimapData = useMemo(() => {
    const matches = currentPair?.matches || [];
    const fileALines = (fileAContent?.content || '').split('\n').length;
    const fileBLines = (fileBContent?.content || '').split('\n').length;
    if (fileALines === 0 || fileBLines === 0) return { a: [], b: [] };

    const buildBlocks = (totalLines: number, isFileA: boolean) =>
      matches.map((m, idx) => {
        const start = isFileA ? m.file_a_start_line : m.file_b_start_line;
        const end = isFileA ? m.file_a_end_line : m.file_b_end_line;
        const top = ((start - 1) / totalLines) * 100;
        const height = Math.max(((end - start + 1) / totalLines) * 100, 0.5);
        const color = MINIMAP_PALETTE[idx % MINIMAP_PALETTE.length];
        return { top, height, color, idx };
      });

    return { a: buildBlocks(fileALines, true), b: buildBlocks(fileBLines, false) };
  }, [currentPair, fileAContent, fileBContent]);

  // Synchronized scrolling
  const handleScrollA = useCallback(() => {
    if (!syncScroll || scrollSyncing.current) return;
    const src = fileAContainerRef.current;
    const dst = fileBContainerRef.current;
    if (!src || !dst) return;
    const ratio = src.scrollHeight > src.clientHeight
      ? src.scrollTop / (src.scrollHeight - src.clientHeight) : 0;
    scrollSyncing.current = true;
    dst.scrollTop = ratio * (dst.scrollHeight - dst.clientHeight);
    requestAnimationFrame(() => { scrollSyncing.current = false; });
  }, [syncScroll]);

  const handleScrollB = useCallback(() => {
    if (!syncScroll || scrollSyncing.current) return;
    const src = fileBContainerRef.current;
    const dst = fileAContainerRef.current;
    if (!src || !dst) return;
    const ratio = src.scrollHeight > src.clientHeight
      ? src.scrollTop / (src.scrollHeight - src.clientHeight) : 0;
    scrollSyncing.current = true;
    dst.scrollTop = ratio * (dst.scrollHeight - dst.clientHeight);
    requestAnimationFrame(() => { scrollSyncing.current = false; });
  }, [syncScroll]);

  useEffect(() => {
    const elA = fileAContainerRef.current;
    const elB = fileBContainerRef.current;
    elA?.addEventListener('scroll', handleScrollA, { passive: true });
    elB?.addEventListener('scroll', handleScrollB, { passive: true });
    return () => {
      elA?.removeEventListener('scroll', handleScrollA);
      elB?.removeEventListener('scroll', handleScrollB);
    };
  }, [handleScrollA, handleScrollB]);

  // Fetch pair data + content
  useEffect(() => {
    if (!selectedFileA || !selectedFileB || !isOpen) return;

    let cancelled = false;

    const fetchPair = async () => {
      try {
        const response = await api.get<ApiPlagiarismResult>(API_ENDPOINTS.FILE_PAIR, {
          params: { file_a: selectedFileA.id, file_b: selectedFileB.id }
        });
        const pairData = response.data;

        setAnalyzingMatches(true);
        try {
          const analyzeResponse = await api.post<{ matches: ApiPlagiarismMatch[]; ast_similarity: number }>(
            API_ENDPOINTS.FILE_PAIR_ANALYZE, null,
            { params: { file_a: selectedFileA.id, file_b: selectedFileB.id } }
          );
          pairData.matches = transformMatches(analyzeResponse.data.matches as unknown as BackendMatch[]);
          pairData.ast_similarity = analyzeResponse.data.ast_similarity;
        } catch {
          pairData.matches = transformMatches(pairData.matches as unknown as BackendMatch[]);
        } finally {
          setAnalyzingMatches(false);
        }

        if (!cancelled) setCurrentPair(pairData);
      } catch (err: unknown) {
        if (!cancelled) {
          if ((err as ApiError).response?.status !== 404) {
            console.error('Error fetching file pair:', err);
          }
          setCurrentPair(null);
        }
      }
    };

    const fetchContent = async () => {
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
        if (!cancelled) {
          setFileAContent(fileAResponse.data);
          setFileBContent(fileBResponse.data);
        }
      } catch (error) {
        if (!cancelled) {
          setContentError(error instanceof Error ? error.message : t('common:errors.failedToLoad'));
        }
      } finally {
        if (!cancelled) setLoadingContent(false);
      }
    };

    fetchPair();
    fetchContent();
    return () => { cancelled = true; };
  }, [selectedFileA, selectedFileB, isOpen]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      const isTextInput = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement;

      if (!isTextInput) {
        // Y = Confirm plagiarism
        if (e.key.toLowerCase() === 'y') {
          e.preventDefault();
          handleConfirmPlagiarism();
          return;
        }

        // N = Clear pair (not plagiarism)
        if (e.key.toLowerCase() === 'n') {
          e.preventDefault();
          handleClearPair();
          return;
        }
      }

      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
        case 'ArrowRight':
          e.preventDefault();
          handleNextPair();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          handlePrevPair();
          break;
        case 'c':
          if (!isTextInput) {
            e.preventDefault();
            setFilterComments(f => !f);
          }
          break;
        case 's':
          if (!isTextInput) {
            e.preventDefault();
            setSyncScroll(f => !f);
          }
          break;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, currentIndex, pairs, onClose]);

  const getLineRef = useCallback((fileA: boolean) => (lineIndex: number, el: HTMLDivElement | null) => {
    if (el) {
      if (fileA) fileALineRefs.current.set(lineIndex, el);
      else fileBLineRefs.current.set(lineIndex, el);
    }
  }, []);

  const handleJumpToMatch = useCallback((clickedLine: number, targetViewportOffset: number, clickedIsFileA: boolean) => {
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

    const targetRect = targetEl.getBoundingClientRect();
    const containerRect = targetContainer.getBoundingClientRect();
    const containerBorderTop = parseFloat(getComputedStyle(targetContainer).borderTopWidth) || 0;
    const targetCurrentOffset = targetRect.top - containerRect.top - containerBorderTop;
    const scrollDelta = targetCurrentOffset - targetViewportOffset;
    targetContainer.scrollTo({ top: targetContainer.scrollTop + scrollDelta, behavior: 'smooth' });
  }, [currentPair]);

  const navigateToIndex = useCallback((idx: number) => {
    if (idx < 0 || idx >= pairs.length) return;
    const pair = pairs[idx];
    setCurrentIndex(idx);
    setSelectedFileA({ id: pair.file_a_id, filename: pair.file_a_name, language: '', task_id: pair.task_id, status: '', similarity: undefined });
    setSelectedFileB({ id: pair.file_b_id, filename: pair.file_b_name, language: '', task_id: pair.task_id, status: '', similarity: undefined });
    setHoveredMatchIndex(null);
    setCurrentPair(null);
    setFileAContent(null);
    setFileBContent(null);
    fileALineRefs.current.clear();
    fileBLineRefs.current.clear();
  }, [pairs]);

  const handleNextPair = useCallback(() => {
    if (pairs.length > 0 && currentIndex < pairs.length - 1) {
      navigateToIndex(currentIndex + 1);
    } else if (onNavigate) {
      onNavigate('next');
    } else if (pairs.length > 0) {
      navigateToIndex(0);
    }
  }, [pairs, currentIndex, navigateToIndex, onNavigate]);

  const handlePrevPair = useCallback(() => {
    if (pairs.length > 0 && currentIndex > 0) {
      navigateToIndex(currentIndex - 1);
    } else if (onNavigate) {
      onNavigate('prev');
    } else if (pairs.length > 0) {
      navigateToIndex(pairs.length - 1);
    }
  }, [pairs, currentIndex, navigateToIndex, onNavigate]);

  const handleConfirmPlagiarism = async () => {
    const resultId = resultIdRef.current;
    if (!resultId) {
      toast({
        title: t('errors.generic'),
        description: t('toasts.pairIdMissing'),
        status: 'error',
        duration: 3000,
      });
      return;
    }
    setConfirming(true);
    try {
      await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(resultId));
      toast({
        title: t('common:toasts.confirmed'),
        description: t('common:toasts.pairMarkedAsPlagiarism'),
        status: 'success',
        duration: 1500,
      });
      if (onActionComplete) onActionComplete('confirm', resultId);
      handleNextPair();
    } catch (error) {
      console.error('Error confirming plagiarism:', error);
      toast({
        title: t('common:errors.generic'),
        description: t('common:toasts.failedToConfirm'),
        status: 'error',
        duration: 3000,
      });
    } finally {
      setConfirming(false);
    }
  };

  const handleClearPair = async () => {
    const resultId = resultIdRef.current;
    if (!resultId) {
      toast({
        title: t('errors.generic'),
        description: t('toasts.pairIdMissing'),
        status: 'error',
        duration: 3000,
      });
      return;
    }
    setClearing(true);
    try {
      await api.post(API_ENDPOINTS.CLEAR_PAIR(resultId));
      toast({
        title: t('common:toasts.cleared'),
        description: t('common:toasts.pairMarkedAsNotPlagiarism'),
        status: 'info',
        duration: 1500,
      });
      if (onActionComplete) onActionComplete('clear', resultId);
      handleNextPair();
    } catch (error) {
      console.error('Error clearing pair:', error);
      toast({
        title: t('common:errors.generic'),
        description: t('common:toasts.failedToClear'),
        status: 'error',
        duration: 3000,
      });
    } finally {
      setClearing(false);
    }
  };

  const currentReviewPair = pairs[currentIndex];

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      placement="right"
      size="full"
    >
      <DrawerOverlay />
      <DrawerContent>
        <DrawerCloseButton />
        <DrawerHeader borderBottomWidth="1px" borderColor={borderColor} bg={headerBg}>
          <Flex align="center" justify="space-between" pr={8}>
            <HStack spacing={3}>
              {currentReviewPair && (
                <>
                  <Text fontSize="sm" color={mutedColor} noOfLines={1}>
                    {currentReviewPair.upload_name || currentReviewPair.assignment_name || ''}
                  </Text>
                  <Text fontSize="sm" color={mutedColor}>/</Text>
                </>
              )}
              <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
                {selectedFileA?.filename} {t('common:vs')} {selectedFileB?.filename}
              </Text>
              {currentPair && (
                <Badge colorScheme={getSimilarityColor(currentPair.ast_similarity)} fontSize="md" px={2} py={1}>
                  {((currentPair.ast_similarity || 0) * 100).toFixed(1)}%
                </Badge>
              )}
              {analyzingMatches && <Spinner size="sm" />}
            </HStack>

            <HStack spacing={1}>
              {pairs.length > 1 && (
                <>
                  <IconButton
                    aria-label="Previous pair"
                    icon={<FiChevronLeft />}
                    size="sm"
                    variant="ghost"
                    onClick={handlePrevPair}
                  />
                  <Text fontSize="xs" color={mutedColor} minW="40px" textAlign="center">
                    {currentIndex + 1}/{pairs.length}
                  </Text>
                  <IconButton
                    aria-label="Next pair"
                    icon={<FiChevronRight />}
                    size="sm"
                    variant="ghost"
                    onClick={handleNextPair}
                  />
                </>
              )}
            </HStack>
          </Flex>
        </DrawerHeader>

        <DrawerBody p={0} display="flex" flexDirection="column" overflow="hidden">
          {/* Toolbar */}
          <Flex borderBottomWidth="1px" borderColor={borderColor} px={3} py={2} gap={2} flexShrink={0}>
            <Tooltip label={filterComments ? 'Show comments' : 'Hide comments'} placement="bottom">
              <IconButton
                aria-label="Toggle comments"
                icon={filterComments ? <FiEye /> : <FiEyeOff />}
                size="sm"
                variant={filterComments ? 'solid' : 'ghost'}
                colorScheme={filterComments ? 'orange' : 'gray'}
                onClick={() => setFilterComments(!filterComments)}
              />
            </Tooltip>
            <Tooltip label={filterEmpty ? 'Show empty lines' : 'Hide empty lines'} placement="bottom">
              <IconButton
                aria-label="Toggle empty lines"
                icon={filterEmpty ? <FiEye /> : <FiFilter />}
                size="sm"
                variant={filterEmpty ? 'solid' : 'ghost'}
                colorScheme={filterEmpty ? 'green' : 'gray'}
                onClick={() => setFilterEmpty(!filterEmpty)}
              />
            </Tooltip>
            <Tooltip label={syntaxHighlight ? 'Disable syntax highlight' : 'Enable syntax highlight'} placement="bottom">
              <IconButton
                aria-label="Toggle syntax highlight"
                icon={<FiCode />}
                size="sm"
                variant={syntaxHighlight ? 'solid' : 'ghost'}
                colorScheme={syntaxHighlight ? 'cyan' : 'gray'}
                onClick={() => setSyntaxHighlight(!syntaxHighlight)}
              />
            </Tooltip>
            <Tooltip label={syncScroll ? 'Unlock scroll sync' : 'Lock scroll sync'} placement="bottom">
              <IconButton
                aria-label="Toggle scroll sync"
                icon={syncScroll ? <FiLink /> : <FiLink2 />}
                size="sm"
                variant={syncScroll ? 'solid' : 'ghost'}
                colorScheme={syncScroll ? 'blue' : 'gray'}
                onClick={() => setSyncScroll(!syncScroll)}
              />
            </Tooltip>

            <Box flex={1} />

            <Text fontSize="xs" color={mutedColor} alignSelf="center">
              {matchStats.totalMatches} matches · {matchStats.coverageA.toFixed(0)}%A · {matchStats.coverageB.toFixed(0)}%B
            </Text>
          </Flex>

          {/* Content */}
          {contentError && (
            <Box px={4} py={2} bg="red.50" borderBottomWidth={1} borderColor="red.200">
              <Text fontSize="sm" color="red.800">{contentError}</Text>
            </Box>
          )}

          {loadingContent ? (
            <Flex flex={1} align="center" justify="center" py={8}>
              <Spinner size="lg" />
              <Text ml={3} color={mutedColor}>Loading...</Text>
            </Flex>
          ) : (
            <Flex flex={1} gap={0} align="stretch" minH={0} overflow="hidden">
              {/* Left minimap */}
              <Box w="16px" bg={minimapBg} position="relative" flexShrink={0}>
                {minimapData.a.map(block => (
                  <Box
                    key={block.idx}
                    position="absolute"
                    left="2px"
                    right="2px"
                    top={`${block.top}%`}
                    h={`${block.height}%`}
                    bg={block.color}
                    borderRadius="1px"
                    minH="2px"
                  />
                ))}
              </Box>

              <Flex flex={1} gap={4} align="stretch" py={4} px={2} minH={0} overflow="hidden">
                <FileViewer
                  content={fileAContent?.content || ''}
                  fileName={fileAContent?.filename || 'File A'}
                  language={fileAContent?.language || 'unknown'}
                  matches={currentPair?.matches || []}
                  isFileA={true}
                  filterComments={filterComments}
                  filterEmpty={filterEmpty}
                  syntaxHighlight={syntaxHighlight}
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
                  isFileA={false}
                  filterComments={filterComments}
                  filterEmpty={filterEmpty}
                  syntaxHighlight={syntaxHighlight}
                  hoveredMatchIndex={hoveredMatchIndex}
                  onHoverMatch={setHoveredMatchIndex}
                  onJumpToMatch={handleJumpToMatch}
                  scrollContainerRef={fileBContainerRef}
                  getLineRef={getLineRef(false)}
                />
              </Flex>

              {/* Right minimap */}
              <Box w="16px" bg={minimapBg} position="relative" flexShrink={0}>
                {minimapData.b.map(block => (
                  <Box
                    key={block.idx}
                    position="absolute"
                    left="2px"
                    right="2px"
                    top={`${block.top}%`}
                    h={`${block.height}%`}
                    bg={block.color}
                    borderRadius="1px"
                    minH="2px"
                  />
                ))}
              </Box>
            </Flex>
          )}
        </DrawerBody>

        <DrawerFooter borderTopWidth="1px" borderColor={borderColor} bg={headerBg} gap={3}>
          <Button
            flex={1}
            colorScheme="green"
            leftIcon={<FiCheck />}
            onClick={handleConfirmPlagiarism}
            isLoading={confirming}
          >
            Confirm (Y)
          </Button>
          <Button
            flex={1}
            colorScheme="gray"
            leftIcon={<FiX />}
            onClick={handleClearPair}
            isLoading={clearing}
          >
            Clear (N)
          </Button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
};

export default ReviewSlideOver;
