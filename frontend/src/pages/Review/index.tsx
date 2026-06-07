import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router';
import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Badge,
  Button,
  Card,
  CardBody,
  Progress,
  useColorModeValue,
  useToast,
  Spinner,
  Icon,
  Select,
  Input,
  InputGroup,
  InputRightElement,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiZap, FiRefreshCw, FiCheckCircle, FiPlayCircle, FiChevronLeft, FiChevronRight } from 'react-icons/fi';
import { useReviewQueue } from '../../hooks/useUploadQueries';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../services/api';
import type { ApiError, ReviewPair, SubjectWithAssignments } from '../../types';
import ReviewSlideOver from '../../components/Review/ReviewSlideOver';
import AssignmentFilter from '../../components/Review/AssignmentFilter';

const PAGE_SIZE_OPTIONS = [25, 50, 100];

const ReviewTabs: React.FC<{
  activeTab: number;
  setActiveTab: (tab: number) => void;
}> = ({ activeTab, setActiveTab }) => {
  const { t } = useTranslation();
  const tabs = [
    { label: t('review:toReview'), color: 'red' },
    { label: t('review:all'), color: 'blue' },
    { label: t('review:confirmed'), color: 'orange' },
    { label: t('review:bulkConfirmed'), color: 'yellow' },
    { label: t('review:cleared'), color: 'green' },
  ];

  return (
    <HStack spacing={1} wrap="wrap" justify="end">
      {tabs.map((tab, idx) => (
        <Button
          key={idx}
          size="sm"
          variant={activeTab === idx ? 'solid' : 'ghost'}
          colorScheme={activeTab === idx ? tab.color : 'gray'}
          onClick={() => setActiveTab(idx)}
        >
          {tab.label}
        </Button>
      ))}
    </HStack>
  );
};

const WINDOW_SIZE = 5;
const WINDOW_HALF = Math.floor(WINDOW_SIZE / 2);

const PaginationControls: React.FC<{
  page: number;
  totalPages: number;
  total: number;
  isFirstPage: boolean;
  isLastPage: boolean;
  isPageLoading: boolean;
  prevPage: () => void;
  nextPage: () => void;
  goToPage: (p: number) => void;
}> = ({ page, totalPages, total, isFirstPage, isLastPage, isPageLoading, prevPage, nextPage, goToPage }) => {
  const [gotoOpen, setGotoOpen] = useState(false);
  const [gotoValue, setGotoValue] = useState('');
  const gotoInputRef = useRef<HTMLInputElement>(null);

  const handleGotoSubmit = () => {
    const target = parseInt(gotoValue, 10);
    if (!isNaN(target) && target >= 1 && target <= totalPages) {
      goToPage(target - 1);
    }
    setGotoOpen(false);
    setGotoValue('');
  };

  const handleGotoKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleGotoSubmit();
    if (e.key === 'Escape') { setGotoOpen(false); setGotoValue(''); }
  };

  const btnMinW = useMemo(() => {
    const digits = String(totalPages).length;
    if (digits <= 2) return '32px';
    return `${32 + (digits - 2) * 8}px`;
  }, [totalPages]);

  const pageSlots = useMemo(() => {
    const T = 7;
    const slots: { type: 'page' | 'ellipsis'; page?: number }[] = [];

    if (totalPages <= T) {
      for (let i = 0; i < totalPages; i++) slots.push({ type: 'page', page: i });
      return slots;
    }

    if (page <= 3) {
      // Start-anchored: show pages 0..4, ellipsis, last
      for (let i = 0; i < 5; i++) slots.push({ type: 'page', page: i });
      slots.push({ type: 'ellipsis' });
      slots.push({ type: 'page', page: totalPages - 1 });
    } else if (page >= totalPages - 4) {
      // End-anchored: first, ellipsis, last 5 pages
      slots.push({ type: 'page', page: 0 });
      slots.push({ type: 'ellipsis' });
      for (let i = totalPages - 5; i < totalPages; i++) slots.push({ type: 'page', page: i });
    } else {
      // Middle: first, ellipsis, page-1/page/page+1, ellipsis, last
      slots.push({ type: 'page', page: 0 });
      slots.push({ type: 'ellipsis' });
      slots.push({ type: 'page', page: page - 1 });
      slots.push({ type: 'page', page: page });
      slots.push({ type: 'page', page: page + 1 });
      slots.push({ type: 'ellipsis' });
      slots.push({ type: 'page', page: totalPages - 1 });
    }

    return slots;
  }, [page, totalPages]);

  return (
    <HStack spacing={1}>
      <Button size="sm" variant="ghost" onClick={prevPage} isDisabled={isFirstPage || total === 0} minW={btnMinW}>
        <FiChevronLeft />
      </Button>
      {pageSlots.map((slot, idx) => {
        if (slot.type === 'ellipsis') {
          return (
            <Button key={`e-${idx}`} size="sm" variant="ghost" isDisabled minW={btnMinW} color="gray.400" _disabled={{ cursor: 'default', opacity: 1 }}>
              …
            </Button>
          );
        }
        const p = slot.page!;
        const isActive = p === page;
        return (
          <Button
            key={p}
            size="sm"
            variant={isActive ? 'solid' : 'ghost'}
            colorScheme={isActive ? 'brand' : 'gray'}
            onClick={() => goToPage(p)}
            minW={btnMinW}
            isLoading={isActive && isPageLoading}
            spinner={<Spinner size="xs" />}
          >
            {p + 1}
          </Button>
        );
      })}
      <Button size="sm" variant="ghost" onClick={nextPage} isDisabled={isLastPage || total === 0} minW={btnMinW}>
        <FiChevronRight />
      </Button>
      {totalPages > 1 && (
        gotoOpen ? (
          <Input
            ref={gotoInputRef}
            size="sm"
            w={btnMinW}
            value={gotoValue}
            onChange={(e) => setGotoValue(e.target.value)}
            onKeyDown={handleGotoKeyDown}
            onBlur={handleGotoSubmit}
            placeholder={`${totalPages}`}
            autoFocus
            type="number"
            min={1}
            max={totalPages}
          />
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setGotoOpen(true)} minW={btnMinW}>
            …
          </Button>
        )
      )}
    </HStack>
  );
};

const ReviewPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState(0);
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [similarityFilter, setSimilarityFilter] = useState('');
  const [pageSize, setPageSize] = useState(50);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [slideOverOpen, setSlideOverOpen] = useState(false);
  const [slideOverPairs, setSlideOverPairs] = useState<ReviewPair[]>([]);
  const [slideOverIndex, setSlideOverIndex] = useState(0);

  const [bulkThreshold, setBulkThreshold] = useState('0.8');
  const [bulkClearThreshold, setBulkClearThreshold] = useState('0.3');
  const [isBulkConfirming, setIsBulkConfirming] = useState(false);
  const [isBulkClearing, setIsBulkClearing] = useState(false);

  const { isOpen: isBulkOpen, onOpen: onBulkOpen, onClose: onBulkClose } = useDisclosure();
  const { isOpen: isBulkClearOpen, onOpen: onBulkClearOpen, onClose: onBulkClearClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const mutedTextColor = useColorModeValue('gray.500', 'gray.400');

  const assignmentId = searchParams.get('assignment_id') || undefined;

  const getCurrentStatus = () => {
    switch (activeTab) {
      case 0: return 'unreviewed';
      case 1: return 'all';
      case 2: return 'plagiarism';
      case 3: return 'bulk_confirmed';
      case 4: return 'clear';
      default: return 'unreviewed';
    }
  };

  const status = getCurrentStatus();

  const [page, setPage] = useState(0);
  const offset = page * pageSize;

  const { data: globalStatus } = useQuery({
    queryKey: ['global-review-status', assignmentId],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (assignmentId) params.assignment_id = assignmentId;
      const res = await api.get('/plagiarism/review-status', { params });
      return res.data;
    },
  });

  const serverMinSimilarity = useMemo(() => {
    if (!similarityFilter.trim()) return undefined;
    const match = similarityFilter.match(/[<>≤≥]?\s*=?\s*([\d.]+)/);
    if (!match) return undefined;
    const threshold = parseFloat(match[1]);
    if (isNaN(threshold)) return undefined;
    const normalized = threshold > 1 ? threshold / 100 : threshold;
    if (similarityFilter.includes('>') || similarityFilter.includes('≥')) return normalized;
    return undefined;
  }, [similarityFilter]);

  const { data, isLoading, isFetching, refetch, error } = useReviewQueue({
    limit: pageSize,
    offset,
    assignment_id: assignmentId,
    min_similarity: serverMinSimilarity,
    status: status === 'all' ? undefined : status,
    search: debouncedSearch || undefined,
  });

  const { data: queueCount } = useQuery({
    queryKey: ['review-queue-count', assignmentId, status, serverMinSimilarity, debouncedSearch],
    queryFn: async () => {
      const params: Record<string, string | number> = {};
      if (assignmentId) params.assignment_id = assignmentId;
      if (status !== 'all') params.status = status;
      if (serverMinSimilarity !== undefined) params.min_similarity = serverMinSimilarity;
      if (debouncedSearch) params.search = debouncedSearch;
      const res = await api.get(API_ENDPOINTS.REVIEW_QUEUE_COUNT, { params });
      return res.data.count as number;
    },
  });

  const { data: subjectsData } = useQuery<SubjectWithAssignments[]>({
    queryKey: ['subjects', 'with-assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.SUBJECTS);
      return res.data.subjects;
    },
  });

  useEffect(() => {
    if (error) {
      const apiError = error as ApiError;
      if (apiError.response?.status === 422) {
        const errorData = apiError.response.data;
        const errorMessage = errorData.detail || 'Invalid input parameters';
        toast({
          title: 'Validation Error',
          description: errorMessage,
          status: 'error',
          duration: 5000,
        });
      } else if (!apiError.response) {
        toast({
          title: 'Network Error',
          description: 'Unable to connect to the server',
          status: 'error',
          duration: 5000,
        });
      }
    }
  }, [error, toast]);

  const pairs = data?.items || [];
  const total = queueCount ?? 0;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, Math.max(0, totalPages - 1));

  const nextPage = useCallback(() => setPage(p => Math.min(p + 1, totalPages - 1)), [totalPages]);
  const prevPage = useCallback(() => setPage(p => Math.max(p - 1, 0)), []);
  const goToPage = useCallback((p: number) => setPage(Math.min(Math.max(p, 0), totalPages - 1)), [totalPages]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setPage(0);
  }, [debouncedSearch, similarityFilter, assignmentId, status, pageSize]);

  const isFirstPage = safePage === 0;
  const isLastPage = safePage >= totalPages - 1;

  const unreviewedCount = globalStatus?.unreviewed ?? 0;
  const totalPairs = globalStatus?.total_pairs ?? 0;

  const selectedAssignmentName = useMemo(() => {
    if (!assignmentId || !subjectsData) return null;
    for (const subject of subjectsData) {
      for (const assignment of subject.assignments || []) {
        if (assignment.id === assignmentId) return assignment.name;
      }
    }
    return null;
  }, [assignmentId, subjectsData]);

  const toggleSelect = (pairId: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(pairId)) next.delete(pairId);
      else next.add(pairId);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === pairs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(pairs.map(p => p.pair_id)));
    }
  };

  const handleAssignmentSelect = (selectedId: string | null) => {
    if (selectedId) {
      setSearchParams(prev => {
        prev.set('assignment_id', selectedId);
        return prev;
      });
    } else {
      setSearchParams(prev => {
        prev.delete('assignment_id');
        return prev;
      });
    }
  };

  const handleBulkConfirm = async () => {
    const threshold = parseFloat(bulkThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({ title: 'Invalid threshold', description: 'Threshold must be between 0 and 1', status: 'error', duration: 3000 });
      return;
    }

    setIsBulkConfirming(true);
    try {
      const endpoint = assignmentId
        ? API_ENDPOINTS.BULK_CONFIRM(assignmentId)
        : API_ENDPOINTS.GLOBAL_BULK_CONFIRM;
      const params: Record<string, number | string> = { threshold };
      if (assignmentId) params.assignment_id = assignmentId;
      const result = await api.post(endpoint, null, { params });
      const count = result.data?.confirmed_pairs ?? 0;
      toast({
        title: 'Bulk confirm complete',
        description: `Confirmed ${count} pair${count !== 1 ? 's' : ''} above ${(threshold * 100).toFixed(0)}% similarity`,
        status: 'success',
        duration: 5000
      });
      onBulkClose();
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
      queryClient.invalidateQueries({ queryKey: ['global-review-status'] });
    } catch (error: unknown) {
      console.error('Bulk confirm failed:', error);
      const apiError = error as ApiError;
      if (apiError.response?.status === 422) {
        toast({ title: 'Validation Error', description: apiError.response?.data?.detail || 'Invalid threshold parameter', status: 'error', duration: 5000 });
      } else {
        toast({ title: 'Bulk confirm failed', description: apiError.response?.data?.detail || 'Unknown error occurred', status: 'error', duration: 3000 });
      }
    } finally {
      setIsBulkConfirming(false);
    }
  };

  const handleBulkClear = async () => {
    const threshold = parseFloat(bulkClearThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({ title: 'Invalid threshold', description: 'Threshold must be between 0 and 1', status: 'error', duration: 3000 });
      return;
    }

    setIsBulkClearing(true);
    try {
      const endpoint = assignmentId
        ? API_ENDPOINTS.BULK_CLEAR(assignmentId)
        : API_ENDPOINTS.GLOBAL_BULK_CLEAR;
      const params: Record<string, number | string> = { threshold };
      if (assignmentId) params.assignment_id = assignmentId;
      const result = await api.post(endpoint, null, { params });
      const count = result.data?.confirmed_pairs ?? 0;
      toast({
        title: 'Bulk clear complete',
        description: `Cleared ${count} pair${count !== 1 ? 's' : ''}`,
        status: 'success',
        duration: 5000
      });
      onBulkClearClose();
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
      queryClient.invalidateQueries({ queryKey: ['global-review-status'] });
    } catch (error: unknown) {
      console.error('Bulk clear failed:', error);
      const apiError = error as ApiError;
      if (apiError.response?.status === 422) {
        toast({ title: 'Validation Error', description: apiError.response?.data?.detail || 'Invalid threshold parameter', status: 'error', duration: 5000 });
      } else {
        toast({ title: 'Bulk clear failed', description: apiError.response?.data?.detail || 'Unknown error occurred', status: 'error', duration: 3000 });
      }
    } finally {
      setIsBulkClearing(false);
    }
  };

  const handlePairClick = (pair: ReviewPair, index: number) => {
    setSelectedIndex(index);
    setSlideOverPairs(pairs);
    setSlideOverIndex(index);
    setSlideOverOpen(true);
  };

  const handleSlideOverAction = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleSlideOverNavigate = useCallback((direction: 'next' | 'prev') => {
    if (direction === 'next') {
      if (selectedIndex < pairs.length - 1) {
        const newIndex = selectedIndex + 1;
        setSelectedIndex(newIndex);
        setSlideOverPairs(pairs);
        setSlideOverIndex(newIndex);
      } else if (!isLastPage) {
        nextPage();
        setSelectedIndex(0);
      }
    } else {
      if (selectedIndex > 0) {
        const newIndex = selectedIndex - 1;
        setSelectedIndex(newIndex);
        setSlideOverPairs(pairs);
        setSlideOverIndex(newIndex);
      } else if (!isFirstPage) {
        prevPage();
        setSelectedIndex(pageSize - 1);
      }
    }
  }, [selectedIndex, pairs, isLastPage, isFirstPage, nextPage, prevPage, pageSize]);

  const handleItemAction = async (pair: ReviewPair) => {
    try {
      await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(pair.pair_id));
      toast({ title: 'Confirmed', description: 'Pair marked as plagiarism', status: 'success', duration: 1500 });
      refetch();
    } catch (error: unknown) {
      console.error('Failed to confirm pair:', error);
      const apiError = error as ApiError;
      if (apiError.response?.status === 422) {
        toast({ title: 'Validation Error', description: apiError.response?.data?.detail || 'Invalid pair ID', status: 'error', duration: 5000 });
      } else {
        toast({ title: 'Failed to confirm', description: apiError.response?.data?.detail || 'Unknown error occurred', status: 'error', duration: 3000 });
      }
    }
  };

  const cardBg = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const selectedBarBg = useColorModeValue('brand.50', 'whiteAlpha.100');

  const bulkConfirmScopeText = assignmentId && selectedAssignmentName
    ? t('review:bulkConfirmScopedDescription', { defaultValue: 'Confirm all unreviewed pairs above {{threshold}}% similarity in "{{assignment}}".', threshold: (parseFloat(bulkThreshold) * 100).toFixed(0), assignment: selectedAssignmentName })
    : t('review:bulkConfirmDescription');

  const bulkClearScopeText = assignmentId && selectedAssignmentName
    ? t('review:bulkClearScopedDescription', { defaultValue: 'Clear all unreviewed pairs ≤ {{threshold}}% similarity in "{{assignment}}".', threshold: (parseFloat(bulkClearThreshold) * 100).toFixed(0), assignment: selectedAssignmentName })
    : t('review:bulkClearDescription');

  return (
    <VStack align="stretch" spacing={4} flex={1} overflow="hidden">
      <Flex justify="space-between" align="center" wrap="wrap" gap={2}>
        <ReviewTabs
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />
        <HStack spacing={2} flexWrap="wrap">
          <Button size="sm" variant="ghost" leftIcon={<FiRefreshCw />} onClick={() => refetch()}>
            {t('common:refresh')}
          </Button>
        </HStack>
      </Flex>

      <Card flexShrink={0} bg={cardBg} borderWidth={1} borderColor={borderColor}>
        <CardBody py={3}>
          <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
            <VStack align="start" spacing={0}>
              <Text fontSize="md" fontWeight="bold">{t('review:toReview')}</Text>
              <Text fontSize="sm" color={mutedTextColor}>
                {t('review:pairsToReview', { count: unreviewedCount })}
              </Text>
            </VStack>
            <HStack spacing={2} flexWrap="wrap">
              <Badge colorScheme="red" fontSize="md" px={3} py={1}>
                {unreviewedCount} {t('review:unreviewed')}
              </Badge>
              {unreviewedCount === 0 && (
                <Badge colorScheme="green" fontSize="md" px={3} py={1}>
                  {t('review:complete')}
                </Badge>
              )}
            </HStack>
          </Flex>
          <Progress
            value={totalPairs > 0 ? ((totalPairs - unreviewedCount) / totalPairs) * 100 : 0}
            w="100%"
            colorScheme={unreviewedCount === 0 ? 'green' : 'red'}
            size="sm"
            borderRadius="full"
            mt={2}
          />
          <HStack mt={3} spacing={2} flexWrap="wrap">
            <Button
              leftIcon={<FiZap />}
              colorScheme="orange"
              size="sm"
              onClick={onBulkOpen}
              disabled={unreviewedCount === 0 || pairs.length === 0}
            >
              {t('review:bulkConfirm')}
            </Button>
            <Button
              leftIcon={<FiZap />}
              colorScheme="green"
              variant="outline"
              size="sm"
              onClick={onBulkClearOpen}
              disabled={unreviewedCount === 0 || pairs.length === 0}
            >
              {t('review:bulkClear')}
            </Button>
            <HStack spacing={2} ml="auto">
              <Button
                leftIcon={<FiPlayCircle />}
                colorScheme="blue"
                size="sm"
                onClick={() => {
                  if (pairs.length > 0) {
                    const firstUnreviewed = pairs.find(p => !p.review_disposition);
                    if (firstUnreviewed) {
                      const index = pairs.indexOf(firstUnreviewed);
                      handlePairClick(firstUnreviewed, index);
                    } else if (pairs.length > 0) {
                      handlePairClick(pairs[0], 0);
                    }
                  }
                }}
                disabled={unreviewedCount === 0 || pairs.length === 0}
              >
                {t('review:startReview')}
              </Button>
            </HStack>
          </HStack>
        </CardBody>
      </Card>

      <HStack spacing={2} wrap="wrap">
        <AssignmentFilter
          selectedAssignmentId={assignmentId ?? null}
          onSelect={handleAssignmentSelect}
        />
        <InputGroup size="sm" maxW={{ base: 'full', md: '200px' }}>
          <Input
            placeholder="Search files..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </InputGroup>
        <InputGroup size="sm" maxW={{ base: 'full', md: '120px' }}>
          <Input
            placeholder="Similarity: <0.5"
            value={similarityFilter}
            onChange={(e) => setSimilarityFilter(e.target.value)}
          />
          <InputRightElement>
            <Text fontSize="xs" color={mutedTextColor}>
              {similarityFilter ? (parseFloat(similarityFilter) * 100 || 0).toFixed(0) + '%' : ''}
            </Text>
          </InputRightElement>
        </InputGroup>
        <Select
          size="sm"
          w={{ base: 'full', md: '100px' }}
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
        >
          {PAGE_SIZE_OPTIONS.map(size => (
            <option key={size} value={size}>{size}</option>
          ))}
        </Select>
      </HStack>

      {selected.size > 0 && (
        <HStack p={3} bg={selectedBarBg} borderRadius="md">
          <Text fontSize="sm" fontWeight="medium">{selected.size} selected</Text>
          <Button size="xs" colorScheme="green" leftIcon={<FiCheckCircle />} onClick={selectAll}>
            Select All
          </Button>
          <Button size="xs" variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </HStack>
      )}

      <Box flex={1} overflowY="auto" css={{
        '&::-webkit-scrollbar': { width: '6px' },
        '&::-webkit-scrollbar-thumb': { bg: 'gray.300', borderRadius: '3px' },
      }}>
        {isLoading ? (
          <Flex justify="center" py={8}><Spinner size="lg" /></Flex>
        ) : pairs.length === 0 ? (
          <Flex justify="center" py={8} flexDirection="column" align="center">
            <Icon as={FiCheckCircle} boxSize={12} color="green.300" mb={4} />
            <Text color="gray.500" fontSize="lg">
              {activeTab === 0 ? t('review:noPairsToReview') : t('review:noPairsFound')}
            </Text>
          </Flex>
        ) : (
          <VStack spacing={2} align="stretch">
            {pairs.map((pair, idx) => (
              <ReviewPairRow
                key={pair.pair_id}
                pair={pair}
                index={idx}
                isSelected={selected.has(pair.pair_id)}
                onSelect={() => toggleSelect(pair.pair_id)}
                onClick={() => handlePairClick(pair, idx)}
                onConfirm={() => handleItemAction(pair)}
              />
            ))}
          </VStack>
        )}
      </Box>

      <Flex justify="space-between" align="center" py={2} wrap="wrap" gap={2}>
        <Box minW="200px">
          <Text fontSize="sm" color="gray.500" whiteSpace="nowrap">
            {t('review:showingRange', { defaultValue: 'Showing {{start}}-{{end}} of {{total}}', start: total === 0 ? 0 : safePage * pageSize + 1, end: Math.min((safePage + 1) * pageSize, total), total })}
          </Text>
        </Box>
        <Flex justify="center" flex={1} minW={0}>
          <PaginationControls
            page={safePage}
          totalPages={totalPages}
          total={total}
          isFirstPage={isFirstPage}
          isLastPage={isLastPage}
          isPageLoading={isFetching}
          prevPage={prevPage}
          nextPage={nextPage}
          goToPage={goToPage}
          />
        </Flex>
        <Box minW="200px" />
      </Flex>

      <ReviewSlideOver
        isOpen={slideOverOpen}
        onClose={() => setSlideOverOpen(false)}
        pairs={slideOverPairs}
        initialIndex={slideOverIndex}
        onActionComplete={handleSlideOverAction}
        onNavigate={handleSlideOverNavigate}
      />

      <AlertDialog isOpen={isBulkOpen} leastDestructiveRef={cancelRef} onClose={onBulkClose}>
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {assignmentId && selectedAssignmentName
                ? t('review:bulkConfirmScopedPairs', { defaultValue: 'Bulk Confirm — {{assignment}}', assignment: selectedAssignmentName })
                : t('review:bulkConfirmPairs')}
            </AlertDialogHeader>
            <AlertDialogBody>
              <VStack align="stretch" spacing={4}>
                <Text>{bulkConfirmScopeText}</Text>
                <InputGroup>
                  <Input
                    placeholder={t('review:thresholdPlaceholder')}
                    value={bulkThreshold}
                    onChange={(e) => setBulkThreshold(e.target.value)}
                  />
                  <InputRightElement>
                    <Text fontSize="sm" color={mutedTextColor} mr={2}>
                      {bulkThreshold ? (parseFloat(bulkThreshold) * 100).toFixed(0) : 0}%
                    </Text>
                  </InputRightElement>
                </InputGroup>
                <Text fontSize="xs" color="orange.500">{t('review:bulkConfirmWarning')}</Text>
              </VStack>
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkClose} isDisabled={isBulkConfirming}>{t('common:cancel')}</Button>
              <Button colorScheme="orange" onClick={handleBulkConfirm} isLoading={isBulkConfirming} loadingText="Confirming..." ml={3}>{t('review:confirmAll')}</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <AlertDialog isOpen={isBulkClearOpen} leastDestructiveRef={cancelRef} onClose={onBulkClearClose}>
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {assignmentId && selectedAssignmentName
                ? t('review:bulkClearScopedPairs', { defaultValue: 'Bulk Clear — {{assignment}}', assignment: selectedAssignmentName })
                : t('review:bulkClearPairs')}
            </AlertDialogHeader>
            <AlertDialogBody>
              <VStack align="stretch" spacing={4}>
                <Text>{bulkClearScopeText}</Text>
                <InputGroup>
                  <Input
                    placeholder={t('review:thresholdPlaceholder')}
                    value={bulkClearThreshold}
                    onChange={(e) => setBulkClearThreshold(e.target.value)}
                    isDisabled={isBulkClearing}
                  />
                  <InputRightElement>
                    <Text fontSize="sm" color={mutedTextColor} mr={2}>
                      {bulkClearThreshold ? (parseFloat(bulkClearThreshold) * 100).toFixed(0) : 0}%
                    </Text>
                  </InputRightElement>
                </InputGroup>
                <Text fontSize="xs" color="gray.500">
                  Clears all unreviewed pairs with similarity ≤ threshold. Lower threshold = fewer pairs cleared.
                </Text>
              </VStack>
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkClearClose} isDisabled={isBulkClearing}>{t('common:cancel')}</Button>
              <Button colorScheme="green" onClick={handleBulkClear} isLoading={isBulkClearing} loadingText="Clearing..." ml={3}>{t('review:clearAll')}</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
};

const getSimilarityColor = (sim: number | null) => {
  if (sim == null) return 'gray';
  if (sim >= 0.8) return 'red';
  if (sim >= 0.5) return 'yellow';
  return 'green';
};

const ReviewPairRow: React.FC<{
  pair: ReviewPair;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
  onClick: () => void;
  onConfirm: () => void;
}> = ({ pair, isSelected, onSelect, onClick, onConfirm }) => {
  const cardBg = useColorModeValue('white', 'gray.700');
  const rowBorderColor = useColorModeValue('gray.200', 'gray.600');
  const hoverBg = useColorModeValue('gray.50', 'gray.600');
  const selectedBorderColor = useColorModeValue('brand.300', 'brand.400');
  const simColor = getSimilarityColor(pair.ast_similarity);

  return (
    <Flex
      p={3}
      bg={cardBg}
      borderRadius="md"
      borderWidth={1}
      borderColor={isSelected ? selectedBorderColor : rowBorderColor}
      align="center"
      gap={3}
      cursor="pointer"
      _hover={{ bg: hoverBg, shadow: 'sm' }}
      onClick={onClick}
    >
      <input
        type="checkbox"
        checked={isSelected}
        onChange={(e) => { e.stopPropagation(); onSelect(); }}
        style={{ width: '16px', height: '16px', cursor: 'pointer' }}
      />

      <Badge colorScheme={simColor} fontSize="sm" minW="60px" textAlign="center">
        {pair.ast_similarity != null ? `${(pair.ast_similarity * 100).toFixed(1)}%` : '—'}
      </Badge>

      <Box flex={1} minW={0}>
        <Text fontWeight="medium" fontSize="sm" noOfLines={1}>
          {pair.file_a_name} ↔ {pair.file_b_name}
        </Text>
        <HStack spacing={2} fontSize="xs" color="gray.500">
          {pair.upload_name && <Text>{pair.upload_name}</Text>}
          {pair.assignment_name && <Text color="purple.500">{pair.assignment_name}</Text>}
        </HStack>
      </Box>

      <Button size="xs" colorScheme="green" variant="ghost" onClick={(e) => { e.stopPropagation(); onConfirm(); }}>
        Confirm
      </Button>
    </Flex>
  );
};

export default ReviewPage;
