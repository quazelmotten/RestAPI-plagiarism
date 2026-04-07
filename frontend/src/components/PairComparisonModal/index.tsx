import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Box,
  Flex,
  HStack,
  VStack,
  Text,
  IconButton,
  Tooltip,
  Badge,
  Collapse,
  Button,
  Spinner,
  useColorModeValue,
} from '@chakra-ui/react';
import {
  FiX,
  FiChevronLeft,
  FiChevronRight,
  FiEye,
  FiEyeOff,
  FiLink,
  FiLink2,
  FiBarChart2,
  FiFolder,
  FiFilter,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../../services/api';
import FileViewer from '../PairComparison/FileViewer';
import FilePickerModal from '../FilePickerModal';
import type {
  FileInfo,
  FileContent,
  PlagiarismResult as ApiPlagiarismResult,
  PlagiarismMatch as ApiPlagiarismMatch,
  ApiError,
} from '../../types';
import { PLAGIARISM_TYPE_COLORS } from '../../types';
import ErrorBoundary from '../ErrorBoundary';

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

interface PairResult extends ApiPlagiarismResult {
  task_id?: string;
}

interface OffenderPair {
  file_a: { id: string; filename: string };
  file_b: { id: string; filename: string };
  ast_similarity: number;
  matches: PlagiarismMatch[];
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

interface PairComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialFileA?: OffenderPair['file_a'] | null;
  initialFileB?: OffenderPair['file_b'] | null;
  pairs?: OffenderPair[];
  assignmentName?: string;
  onNavigatePair?: (pair: OffenderPair, index: number) => void;
}

const getSimilarityGradient = (similarity: number): string => {
  if (similarity >= 0.8) return 'linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%)';
  if (similarity >= 0.5) return 'linear-gradient(135deg, #ffa726 0%, #fb8c00 100%)';
  if (similarity >= 0.3) return 'linear-gradient(135deg, #ffca28 0%, #ffb300 100%)';
  return 'linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)';
};

const PairComparisonModal: React.FC<PairComparisonModalProps> = ({
  isOpen,
  onClose,
  initialFileA,
  initialFileB,
  pairs = [],
  assignmentName,
}) => {
  const { t } = useTranslation(['pairComparison', 'common']);

  const [currentPair, setCurrentPair] = useState<PairResult | null>(null);
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
  const [syncScroll, setSyncScroll] = useState(true);
  const [statsOpen, setStatsOpen] = useState(false);
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  const scrollSyncing = useRef(false);

  const overlayBg = useColorModeValue('gray.50', 'gray.900');
  const headerBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const minimapBg = useColorModeValue('gray.100', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const fileAContainerRef = useRef<HTMLDivElement>(null);
  const fileBContainerRef = useRef<HTMLDivElement>(null);
  const fileALineRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const fileBLineRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Navigate between pairs
  const currentIndex = useMemo(() => {
    if (!selectedFileA || !selectedFileB || pairs.length === 0) return -1;
    return pairs.findIndex(
      p => p.file_a.id === selectedFileA.id && p.file_b.id === selectedFileB.id
    );
  }, [selectedFileA, selectedFileB, pairs]);

  const navigateToIndex = useCallback((idx: number) => {
    if (idx < 0 || idx >= pairs.length) return;
    const pair = pairs[idx];
    setSelectedFileA({ id: pair.file_a.id, filename: pair.file_a.filename, language: '', task_id: '', status: '' });
    setSelectedFileB({ id: pair.file_b.id, filename: pair.file_b.filename, language: '', task_id: '', status: '' });
    setHoveredMatchIndex(null);
    fileALineRefs.current.clear();
    fileBLineRefs.current.clear();
  }, [pairs]);

  // Initialize from props
  useEffect(() => {
    if (isOpen && initialFileA && initialFileB) {
      setSelectedFileA({ id: initialFileA.id, filename: initialFileA.filename, language: '', task_id: '', status: '' });
      setSelectedFileB({ id: initialFileB.id, filename: initialFileB.filename, language: '', task_id: '', status: '' });
      setHoveredMatchIndex(null);
      setCurrentPair(null);
      setFileAContent(null);
      setFileBContent(null);
    }
  }, [isOpen, initialFileA, initialFileB]);

  // Match statistics (ignore blank lines and comments)
  const matchStats = useMemo(() => {
    const matches = currentPair?.matches || [];

    // Compute effective line sets (non-blank, non-comment)
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

    const stats: Record<number, { count: number; linesA: number; linesB: number }> = {};
    let totalLinesA = 0;
    let totalLinesB = 0;

    for (const m of matches) {
      const type = m.plagiarism_type ?? 1;
      if (!stats[type]) stats[type] = { count: 0, linesA: 0, linesB: 0 };
      stats[type].count++;

      // Count effective lines in the range for A
      let countA = 0;
      for (let i = m.file_a_start_line - 1; i <= m.file_a_end_line - 1; i++) {
        if (effectiveA.has(i)) countA++;
      }
      // For B
      let countB = 0;
      for (let i = m.file_b_start_line - 1; i <= m.file_b_end_line - 1; i++) {
        if (effectiveB.has(i)) countB++;
      }

      stats[type].linesA += countA;
      stats[type].linesB += countB;
      totalLinesA += countA;
      totalLinesB += countB;
    }

    return {
      byType: stats,
      totalMatches: matches.length,
      totalLinesA,
      totalLinesB,
      coverageA: totalEffectiveA > 0 ? (totalLinesA / totalEffectiveA) * 100 : 0,
      coverageB: totalEffectiveB > 0 ? (totalLinesB / totalEffectiveB) * 100 : 0,
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
        const color = PLAGIARISM_TYPE_COLORS[m.plagiarism_type ?? 1] || 'rgba(255,235,59,0.4)';
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
          setContentError(error instanceof Error ? error.message : 'Failed to load file contents');
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
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
        case 'n': {
          e.preventDefault();
          if (pairs.length > 0) {
            const nextIdx = currentIndex < pairs.length - 1 ? currentIndex + 1 : 0;
            navigateToIndex(nextIdx);
          }
          break;
        }
        case 'p': {
          e.preventDefault();
          if (pairs.length > 0) {
            const prevIdx = currentIndex > 0 ? currentIndex - 1 : pairs.length - 1;
            navigateToIndex(prevIdx);
          }
          break;
        }
        case 'c':
          e.preventDefault();
          setFilterComments(f => !f);
          break;
        case 's':
          e.preventDefault();
          setSyncScroll(f => !f);
          break;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, currentIndex, pairs, navigateToIndex, onClose]);

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

  if (!isOpen) return null;

  return (
    <Box
      position="absolute"
      top={0}
      left={0}
      right={0}
      bottom={0}
      bg={overlayBg}
      zIndex={100}
      display="flex"
      flexDirection="column"
      overflow="hidden"
    >
      {/* Header with breadcrumbs */}
      <Flex
        bg={headerBg}
        borderBottomWidth="1px"
        borderColor={borderColor}
        px={4}
        py={2}
        align="center"
        justify="space-between"
        flexShrink={0}
        gap={3}
      >
        <HStack spacing={2} flex={1} minW={0}>
          {assignmentName && (
            <>
              <Text fontSize="sm" color={mutedColor} flexShrink={0}>{assignmentName}</Text>
              <Text fontSize="sm" color={mutedColor}>/</Text>
            </>
          )}
          <Button
            size="sm"
            leftIcon={<FiFolder />}
            variant="outline"
            onClick={() => setIsPickerOpen(true)}
            flexShrink={1}
            minW={0}
          >
            <Text noOfLines={1} fontSize="sm">
              {selectedFileA && selectedFileB
                ? `${selectedFileA.filename} ${t('common:vs')} ${selectedFileB.filename}`
                : t('header.noSelection')}
            </Text>
          </Button>

          {currentPair && (
            <Box
              px={4}
              py={1.5}
              borderRadius="lg"
              bg={getSimilarityGradient(currentPair.ast_similarity || 0)}
              color="white"
              fontWeight="bold"
              fontSize="md"
              flexShrink={0}
            >
              {((currentPair.ast_similarity || 0) * 100).toFixed(1)}%
            </Box>
          )}

          {analyzingMatches && <Spinner size="sm" />}

          {/* Pair navigation */}
          {pairs.length > 1 && currentIndex >= 0 && (
            <HStack spacing={1} flexShrink={0}>
              <IconButton
                aria-label="Previous pair"
                icon={<FiChevronLeft />}
                size="sm"
                variant="ghost"
                onClick={() => navigateToIndex(currentIndex > 0 ? currentIndex - 1 : pairs.length - 1)}
              />
              <Text fontSize="xs" color={mutedColor} whiteSpace="nowrap">
                {currentIndex + 1}/{pairs.length}
              </Text>
              <IconButton
                aria-label="Next pair"
                icon={<FiChevronRight />}
                size="sm"
                variant="ghost"
                onClick={() => navigateToIndex(currentIndex < pairs.length - 1 ? currentIndex + 1 : 0)}
              />
            </HStack>
          )}
        </HStack>

        <HStack spacing={1} flexShrink={0}>
          <Tooltip label={filterComments ? t('page.tooltip.showComments') : t('page.tooltip.hideComments')} placement="bottom">
            <IconButton
              aria-label="Toggle comments"
              icon={filterComments ? <FiEye /> : <FiEyeOff />}
              size="sm"
              variant={filterComments ? 'solid' : 'ghost'}
              colorScheme={filterComments ? 'orange' : 'gray'}
              onClick={() => setFilterComments(!filterComments)}
            />
          </Tooltip>
          <Tooltip label={filterEmpty ? t('page.tooltip.showEmptyLines') : t('page.tooltip.hideEmptyLines')} placement="bottom">
            <IconButton
              aria-label="Toggle empty lines"
              icon={filterEmpty ? <FiEye /> : <FiFilter />}
              size="sm"
              variant={filterEmpty ? 'solid' : 'ghost'}
              colorScheme={filterEmpty ? 'green' : 'gray'}
              onClick={() => setFilterEmpty(!filterEmpty)}
            />
          </Tooltip>
          <Tooltip label={syncScroll ? t('page.tooltip.unlockScrollSync') : t('page.tooltip.lockScrollSync')} placement="bottom">
            <IconButton
              aria-label="Toggle scroll sync"
              icon={syncScroll ? <FiLink /> : <FiLink2 />}
              size="sm"
              variant={syncScroll ? 'solid' : 'ghost'}
              colorScheme={syncScroll ? 'blue' : 'gray'}
              onClick={() => setSyncScroll(!syncScroll)}
            />
          </Tooltip>
          <Tooltip label={t('page.tooltip.matchStatistics')} placement="bottom">
            <IconButton
              aria-label="Match statistics"
              icon={<FiBarChart2 />}
              size="sm"
              variant={statsOpen ? 'solid' : 'ghost'}
              colorScheme={statsOpen ? 'purple' : 'gray'}
              onClick={() => setStatsOpen(!statsOpen)}
            />
          </Tooltip>
          <IconButton
            aria-label="Close"
            icon={<FiX />}
            size="sm"
            variant="ghost"
            onClick={onClose}
          />
        </HStack>
      </Flex>

      {/* Stats bar */}
      <Collapse in={statsOpen} animateOpacity>
        <Box px={4} py={2} borderBottomWidth={1} borderColor={borderColor} bg={headerBg}>
          <HStack spacing={6} wrap="wrap">
            <VStack spacing={0} align="start">
              <Text fontSize="xs" color="gray.500">{t('page.stats.totalMatches')}</Text>
              <Text fontWeight="bold">{matchStats.totalMatches}</Text>
            </VStack>
            <VStack spacing={0} align="start">
              <Text fontSize="xs" color="gray.500">{t('page.stats.coverageA')}</Text>
              <Text fontWeight="bold">{matchStats.coverageA.toFixed(1)}%</Text>
            </VStack>
            <VStack spacing={0} align="start">
              <Text fontSize="xs" color="gray.500">{t('page.stats.coverageB')}</Text>
              <Text fontWeight="bold">{matchStats.coverageB.toFixed(1)}%</Text>
            </VStack>
            {Object.entries(matchStats.byType).map(([type, s]) => (
              <HStack key={type} spacing={1}>
                <Badge colorScheme={
                  Number(type) === 1 ? 'green' :
                  Number(type) === 2 ? 'yellow' :
                  Number(type) === 3 ? 'blue' : 'red'
                }>
                  T{type}
                </Badge>
                <Text fontSize="sm">
                  {t('page.stats.matchLineInfo', { count: s.count, linesA: s.linesA, linesB: s.linesB })}
                </Text>
              </HStack>
            ))}
          </HStack>
        </Box>
      </Collapse>

      {/* Content */}
      {contentError && (
        <Box px={4} py={2} bg="red.50" borderBottomWidth={1} borderColor="red.200">
          <Text fontSize="sm" color="red.800">{contentError}</Text>
        </Box>
      )}

      {loadingContent ? (
        <Flex flex={1} align="center" justify="center" py={8} minH={0}>
          <Spinner size="lg" />
          <Text ml={3} color={mutedColor}>{t('page.loading')}</Text>
        </Flex>
      ) : (
        <ErrorBoundary>
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
                fileName={fileAContent?.filename || t('filePicker.fileA')}
                language={fileAContent?.language || 'unknown'}
                matches={currentPair?.matches || []}
                isFileA={true}
                filterComments={filterComments}
                filterEmpty={filterEmpty}
                hoveredMatchIndex={hoveredMatchIndex}
                onHoverMatch={setHoveredMatchIndex}
                onJumpToMatch={handleJumpToMatch}
                scrollContainerRef={fileAContainerRef}
                getLineRef={getLineRef(true)}
              />
              <FileViewer
                content={fileBContent?.content || ''}
                fileName={fileBContent?.filename || t('filePicker.fileB')}
                language={fileBContent?.language || 'unknown'}
                matches={currentPair?.matches || []}
                isFileA={false}
                filterComments={filterComments}
                filterEmpty={filterEmpty}
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
};

export default PairComparisonModal;
