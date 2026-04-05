import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Box,
  Spinner,
  Text,
  useColorModeValue,
  Flex,
  IconButton,
  HStack,
  VStack,
  Tooltip,
  Badge,
  Collapse,
  Button,
  Skeleton,
} from '@chakra-ui/react';
import { FiEye, FiEyeOff, FiChevronUp, FiChevronDown, FiLink, FiLink2, FiBarChart2 } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../services/api';
import FilePickerModal from '../components/FilePickerModal';
import { useSearchParams } from 'react-router';
import type { FileInfo, FileContent, PlagiarismResult as ApiPlagiarismResult, PlagiarismMatch as ApiPlagiarismMatch, ApiError } from '../types';
import { PLAGIARISM_TYPE_LABELS, PLAGIARISM_TYPE_COLORS } from '../types';
import ErrorBoundary from '../components/ErrorBoundary';

type PlagiarismMatch = ApiPlagiarismMatch;

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
  const { t } = useTranslation(['pairComparison', 'common']);
  const [currentPair, setCurrentPair] = useState<PairResult | null>(null);
  const [selectedFileA, setSelectedFileA] = useState<FileInfo | null>(null);
  const [selectedFileB, setSelectedFileB] = useState<FileInfo | null>(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [fileAContent, setFileAContent] = useState<FileContent | null>(null);
  const [fileBContent, setFileBContent] = useState<FileContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [contentError, setContentError] = useState<string | null>(null);
  const [hoveredMatchIndex, setHoveredMatchIndex] = useState<number | null>(null);
  const [analyzingMatches, setAnalyzingMatches] = useState(false);
  const [filterComments, setFilterComments] = useState(false);
  const [headerVisible, setHeaderVisible] = useState(true);
  const [syncScroll, setSyncScroll] = useState(true);
  const [statsOpen, setStatsOpen] = useState(false);
  const scrollSyncing = useRef(false);

  const [searchParams] = useSearchParams();

  const fileAContainerRef = useRef<HTMLDivElement>(null);
  const fileBContainerRef = useRef<HTMLDivElement>(null);
  const fileALineRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const fileBLineRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const bgColor = useColorModeValue('white', 'gray.800');
  const minimapBg = useColorModeValue('gray.100', 'gray.700');

  const currentPairMemo = useMemo(() => currentPair, [currentPair]);

  const isFileAInPair = useMemo(() => {
    if (!currentPairMemo) return false;
    return currentPairMemo.file_a.id === (selectedFileA ? selectedFileA.id : undefined);
  }, [currentPairMemo, selectedFileA]);

  const matchStats = useMemo(() => {
    const matches = currentPairMemo?.matches || [];
    const stats: Record<number, { count: number; linesA: number; linesB: number }> = {};
    let totalLinesA = 0;
    let totalLinesB = 0;

    for (const m of matches) {
      const type = m.plagiarism_type ?? 1;
      if (!stats[type]) stats[type] = { count: 0, linesA: 0, linesB: 0 };
      stats[type].count++;
      const la = m.file_a_end_line - m.file_a_start_line + 1;
      const lb = m.file_b_end_line - m.file_b_start_line + 1;
      stats[type].linesA += la;
      stats[type].linesB += lb;
      totalLinesA += la;
      totalLinesB += lb;
    }

    const fileALines = (fileAContent?.content || '').split('\n').length;
    const fileBLines = (fileBContent?.content || '').split('\n').length;

    return {
      byType: stats,
      totalMatches: matches.length,
      totalLinesA,
      totalLinesB,
      coverageA: fileALines > 0 ? (totalLinesA / fileALines) * 100 : 0,
      coverageB: fileBLines > 0 ? (totalLinesB / fileBLines) * 100 : 0,
    };
  }, [currentPairMemo, fileAContent, fileBContent]);

  const minimapData = useMemo(() => {
    const matches = currentPairMemo?.matches || [];
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

    return {
      a: buildBlocks(fileALines, true),
      b: buildBlocks(fileBLines, false),
    };
  }, [currentPairMemo, fileAContent, fileBContent]);

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

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (!e.ctrlKey && !e.metaKey) return;

      switch (e.key.toLowerCase()) {
        case 'n': {
          e.preventDefault();
          const matches = currentPairMemo?.matches || [];
          if (matches.length === 0) break;
          const next = hoveredMatchIndex === null ? 0 : (hoveredMatchIndex + 1) % matches.length;
          setHoveredMatchIndex(next);
          const m = matches[next];
          const el = fileALineRefs.current.get(m.file_a_start_line - 1);
          el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          break;
        }
        case 'p': {
          e.preventDefault();
          const matches2 = currentPairMemo?.matches || [];
          if (matches2.length === 0) break;
          const prev = hoveredMatchIndex === null ? matches2.length - 1 : (hoveredMatchIndex - 1 + matches2.length) % matches2.length;
          setHoveredMatchIndex(prev);
          const m2 = matches2[prev];
          const el2 = fileALineRefs.current.get(m2.file_a_start_line - 1);
          el2?.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
  }, [currentPairMemo, hoveredMatchIndex]);

  useEffect(() => {
    const fileAId = searchParams.get('file_a');
    const fileBId = searchParams.get('file_b');
    if (fileAId && fileBId && !selectedFileA && !selectedFileB) {
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

  const fetchAllData = useCallback(async () => {
    if (!selectedFileA || !selectedFileB) return;

    setLoadingContent(true);
    setContentError(null);
    fileALineRefs.current.clear();
    fileBLineRefs.current.clear();

    const pairPromise = api.get<ApiPlagiarismResult>(API_ENDPOINTS.FILE_PAIR, {
      params: { file_a: selectedFileA.id, file_b: selectedFileB.id },
    });

    const analyzePromise = api.post<{ matches: ApiPlagiarismMatch[]; ast_similarity: number }>(
      API_ENDPOINTS.FILE_PAIR_ANALYZE, null,
      { params: { file_a: selectedFileA.id, file_b: selectedFileB.id } },
    ).catch(() => null);

    const contentPromise = Promise.all([
      api.get<FileContent>(API_ENDPOINTS.FILE_CONTENT(selectedFileA.id)),
      api.get<FileContent>(API_ENDPOINTS.FILE_CONTENT(selectedFileB.id)),
    ]);

    try {
      const [pairResponse, analyzeResponse, contentResponses] = await Promise.all([
        pairPromise,
        analyzePromise,
        contentPromise,
      ]);

      const pairData = pairResponse.data;

      if (analyzeResponse) {
        pairData.matches = transformMatches(analyzeResponse.data.matches as unknown as BackendMatch[]);
        pairData.ast_similarity = analyzeResponse.data.ast_similarity;
      } else {
        pairData.matches = transformMatches(pairData.matches as unknown as BackendMatch[]);
      }

      setCurrentPair(pairData);
      setFileAContent(contentResponses[0].data);
      setFileBContent(contentResponses[1].data);
    } catch (error) {
      const apiError = error as ApiError;
      if (apiError.response?.status !== 404) {
        console.error('Error fetching comparison data:', error);
      }
      setContentError(error instanceof Error ? error.message : 'Failed to load comparison');
      setCurrentPair(null);
    } finally {
      setLoadingContent(false);
      setAnalyzingMatches(false);
    }
  }, [selectedFileA, selectedFileB]);

  useEffect(() => {
    if (selectedFileA && selectedFileB) {
      setAnalyzingMatches(true);
      fetchAllData();
    } else {
      setCurrentPair(null);
      setFileAContent(null);
      setFileBContent(null);
    }
  }, [selectedFileA, selectedFileB, fetchAllData]);

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

    const targetRect = targetEl.getBoundingClientRect();
    const containerRect = targetContainer.getBoundingClientRect();
    const containerBorderTop = parseFloat(getComputedStyle(targetContainer).borderTopWidth) || 0;
    const targetCurrentOffset = targetRect.top - containerRect.top - containerBorderTop;
    const scrollDelta = targetCurrentOffset - targetViewportOffset;
    const newScrollTop = targetContainer.scrollTop + scrollDelta;

    targetContainer.scrollTo({ top: newScrollTop, behavior: 'smooth' });
  }, [currentPairMemo]);

  const isLoadingInitial = loadingContent && !currentPair && !fileAContent;

  return (
    <Box h="100vh" display="flex" flexDir="column" overflow="hidden">
      {isLoadingInitial ? (
        <Box flex={1} display="flex" alignItems="center" justifyContent="center" py={8} minH={0}>
          <VStack spacing={4}>
            <Skeleton height="40px" width="300px" />
            <Skeleton height="200px" width="80%" />
          </VStack>
        </Box>
      ) : (
        <>
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
              <Tooltip label={t('page.showHeader')} placement="bottom">
                <IconButton
                  aria-label={t('page.showHeader')}
                  icon={<FiChevronDown />}
                  size="sm"
                  variant="ghost"
                  onClick={() => setHeaderVisible(true)}
                />
              </Tooltip>
              {currentPair && (
                <Text fontSize="sm" fontWeight="bold" ml={2}>
                  {t('page.similarity', { percent: ((currentPair.ast_similarity || 0) * 100).toFixed(1) })}
                </Text>
              )}
            </HStack>
          )}

          <HStack px={2} py={1} flexShrink={0} spacing={1}>
            <Tooltip label={filterComments ? t('page.tooltip.showComments') : t('page.tooltip.hideComments')} placement="bottom">
              <IconButton
                aria-label={filterComments ? t('page.aria.showComments') : t('page.aria.hideComments')}
                icon={filterComments ? <FiEye /> : <FiEyeOff />}
                size="sm"
                variant={filterComments ? 'solid' : 'ghost'}
                colorScheme={filterComments ? 'orange' : 'gray'}
                onClick={() => setFilterComments(!filterComments)}
              />
            </Tooltip>
             <Tooltip label={syncScroll ? t('page.tooltip.unlockScrollSync') : t('page.tooltip.lockScrollSync')} placement="bottom">
               <IconButton
                 aria-label={syncScroll ? t('page.aria.unlockScrollSync') : t('page.aria.lockScrollSync')}
                 icon={syncScroll ? <FiLink /> : <FiLink2 />}
                 size="sm"
                 variant={syncScroll ? 'solid' : 'ghost'}
                 colorScheme={syncScroll ? 'blue' : 'gray'}
                 onClick={() => setSyncScroll(!syncScroll)}
               />
             </Tooltip>
             <Tooltip label={t('page.tooltip.matchStatistics')} placement="bottom">
               <IconButton
                 aria-label={t('page.aria.matchStatistics')}
                 icon={<FiBarChart2 />}
                 size="sm"
                 variant={statsOpen ? 'solid' : 'ghost'}
                 colorScheme={statsOpen ? 'purple' : 'gray'}
                 onClick={() => setStatsOpen(!statsOpen)}
               />
             </Tooltip>
            {headerVisible && (
              <Tooltip label={t('page.hideHeader')} placement="bottom">
                <IconButton
                  aria-label={t('page.hideHeader')}
                  icon={<FiChevronUp />}
                  size="sm"
                  variant="ghost"
                  onClick={() => setHeaderVisible(false)}
                />
              </Tooltip>
            )}
          </HStack>

          <Collapse in={statsOpen} animateOpacity>
            <Box px={4} py={2} borderBottomWidth={1} borderColor={useColorModeValue('gray.200', 'gray.600')}>
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
                     <Text fontSize="sm">{t('page.stats.matchLineInfo', { count: s.count, linesA: s.linesA, linesB: s.linesB })}</Text>
                   </HStack>
                 ))}
              </HStack>
            </Box>
          </Collapse>

          {contentError && !loadingContent ? (
            <Box flex={1} display="flex" alignItems="center" justifyContent="center" py={8} minH={0}>
              <Text color="red.500">{contentError}</Text>
            </Box>
          ) : (
            <ErrorBoundary>
              <Flex flex={1} gap={0} align="stretch" minH={0} overflow="hidden">
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
                     fileName={fileBContent?.filename || t('filePicker.fileB')}
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
        </>
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
