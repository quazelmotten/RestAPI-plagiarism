import React, { useState, useCallback } from 'react';
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
  Tooltip,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiZap, FiDownload, FiRefreshCw, FiHelpCircle, FiCheckCircle } from 'react-icons/fi';
import { useReviewQueue, useUpdateUpload } from '../../hooks/useUploadQueries';
import { useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../services/api';
import type { ReviewPair, ReviewQueueResponse } from '../../types';
import ReviewSlideOver from '../../components/Review/ReviewSlideOver';
import { useBulkClear } from '../../hooks/useGrading';

const PAGE_SIZE = 50;

const ReviewTabs: React.FC<{
  activeTab: number;
  setActiveTab: (tab: number) => void;
  unreviewedCount: number;
  totalCount: number;
  confirmedCount: number;
  clearedCount: number;
}> = ({ activeTab, setActiveTab, unreviewedCount, totalCount, confirmedCount, clearedCount }) => {
  const { t } = useTranslation();
  const tabs = [
    { label: t('review:toReview'), count: unreviewedCount, color: 'red' },
    { label: t('review:all'), count: totalCount, color: 'blue' },
    { label: t('review:confirmed'), count: confirmedCount, color: 'orange' },
    { label: t('review:cleared'), count: clearedCount, color: 'green' },
  ];

  return (
    <HStack spacing={1} wrap="wrap">
      {tabs.map((tab, idx) => (
        <Button
          key={idx}
          size="sm"
          variant={activeTab === idx ? 'solid' : 'ghost'}
          colorScheme={activeTab === idx ? tab.color : 'gray'}
          onClick={() => setActiveTab(idx)}
        >
          {tab.label}
          {tab.count > 0 && (
            <Badge ml={1} colorScheme={tab.color} variant="solid" fontSize="xs">
              {tab.count}
            </Badge>
          )}
        </Button>
      ))}
    </HStack>
  );
};

const ReviewPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToast();

  const [activeTab, setActiveTab] = useState(0);
  const [searchFilter, setSearchFilter] = useState('');
  const [similarityFilter, setSimilarityFilter] = useState('');
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [slideOverOpen, setSlideOverOpen] = useState(false);
  const [pairList, setPairList] = useState<ReviewPair[]>([]);

  const [bulkThreshold, setBulkThreshold] = useState('0.8');
  const [bulkClearThreshold, setBulkClearThreshold] = useState('0');

  const { isOpen: isBulkOpen, onOpen: onBulkOpen, onClose: onBulkClose } = useDisclosure();
  const { isOpen: isBulkClearOpen, onOpen: onBulkClearOpen, onClose: onBulkClearClose } = useDisclosure();
  const { isOpen: isHelpOpen, onOpen: onHelpOpen, onClose: onHelpClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const mutedTextColor = useColorModeValue('gray.500', 'gray.400');

  const assignmentId = searchParams.get('assignment_id') || undefined;

  const getCurrentStatus = () => {
    switch (activeTab) {
      case 0: return undefined;
      case 1: return 'all';
      case 2: return 'plagiarism';
      case 3: return 'clear';
      default: return undefined;
    }
  };

  const status = getCurrentStatus();

  const { data, isLoading, refetch } = useReviewQueue({
    limit: pageSize,
    offset: 0,
    assignment_id: assignmentId,
    min_similarity: parseFloat(similarityFilter) || undefined,
    status: status === 'all' ? undefined : status,
  });

  const { data: assignmentsData } = useQuery({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });
  const assignments = assignmentsData?.items || [];

  const pairs = data?.items || [];
  const total = data?.total || 0;

  const unreviewedCount = activeTab === 0 ? total : (data?.total || 0);
  const confirmedCount = activeTab === 2 ? total : 0;
  const clearedCount = activeTab === 3 ? total : 0;

  const filterBySearch = useCallback((items: ReviewPair[]) => {
    if (!searchFilter.trim()) return items;
    const q = searchFilter.toLowerCase();
    return items.filter(item =>
      (item.file_a_name || '').toLowerCase().includes(q) ||
      (item.file_b_name || '').toLowerCase().includes(q)
    );
  }, [searchFilter]);

  const filterBySimilarity = useCallback((items: ReviewPair[]) => {
    if (!similarityFilter.trim()) return items;
    const match = similarityFilter.match(/[<>≤≥]?\s*=?\s*([\d.]+)/);
    if (!match) return items;

    const threshold = parseFloat(match[1]);
    if (isNaN(threshold)) return items;

    const normalizedThreshold = threshold > 1 ? threshold / 100 : threshold;

    if (similarityFilter.includes('>') || similarityFilter.includes('≥')) {
      return items.filter(item => (item.ast_similarity || 0) >= normalizedThreshold);
    } else if (similarityFilter.includes('<') || similarityFilter.includes('≤')) {
      return items.filter(item => (item.ast_similarity || 0) <= normalizedThreshold);
    }
    return items.filter(item => (item.ast_similarity || 0) <= normalizedThreshold);
  }, [similarityFilter]);

  const currentItems = filterBySimilarity(filterBySearch(pairs));

  const toggleSelect = (pairId: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(pairId)) next.delete(pairId);
      else next.add(pairId);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === currentItems.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(currentItems.map(p => p.pair_id)));
    }
  };

  const handleBulkConfirm = async () => {
    const threshold = parseFloat(bulkThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({ title: 'Invalid threshold', description: 'Threshold must be between 0 and 1', status: 'error', duration: 3000 });
      return;
    }

    try {
      let confirmed = 0;
      for (const pair of currentItems) {
        if ((pair.ast_similarity || 0) >= threshold) {
          await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(pair.pair_id));
          confirmed++;
        }
      }
      toast({ title: 'Bulk confirm complete', description: `${confirmed} pairs confirmed`, status: 'success', duration: 3000 });
      onBulkClose();
      refetch();
    } catch {
      toast({ title: 'Bulk confirm failed', status: 'error', duration: 3000 });
    }
  };

  const bulkClearMutation = useBulkClear();

  const handleBulkClear = async () => {
    const threshold = parseFloat(bulkClearThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({ title: 'Invalid threshold', description: 'Threshold must be between 0 and 1', status: 'error', duration: 3000 });
      return;
    }

    try {
      let cleared = 0;
      for (const pair of currentItems) {
        if ((pair.ast_similarity || 0) <= threshold) {
          await api.post(API_ENDPOINTS.CLEAR_PAIR(pair.pair_id));
          cleared++;
        }
      }
      toast({ title: 'Bulk clear complete', description: `${cleared} pairs cleared`, status: 'success', duration: 3000 });
      onBulkClearClose();
      refetch();
    } catch {
      toast({ title: 'Bulk clear failed', status: 'error', duration: 3000 });
    }
  };

  const handlePairClick = (pair: ReviewPair, index: number) => {
    setSelectedIndex(index);
    setPairList(currentItems);
    setSlideOverOpen(true);
  };

  const handleSlideOverAction = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleItemAction = async (pair: ReviewPair) => {
    try {
      await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(pair.pair_id));
      toast({ title: 'Confirmed', description: 'Pair marked as plagiarism', status: 'success', duration: 1500 });
      refetch();
    } catch {
      toast({ title: 'Failed to confirm', status: 'error', duration: 3000 });
    }
  };

  const cardBg = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const handlePrevItem = () => {
    if (selectedIndex > 0) {
      setSelectedIndex(selectedIndex - 1);
    }
  };

  const handleNextItem = () => {
    if (selectedIndex < currentItems.length - 1) {
      setSelectedIndex(selectedIndex + 1);
    }
  };

  return (
    <VStack align="stretch" spacing={4} flex={1} overflow="hidden">
      <Flex justify="space-between" align="center" wrap="wrap" gap={2}>
        <Text fontSize="2xl" fontWeight="bold">{t('review')}</Text>
        <HStack spacing={2}>
          <Tooltip label="Keyboard shortcuts">
            <Button size="sm" variant="ghost" leftIcon={<FiHelpCircle />} onClick={onHelpOpen}>
              {t('common:buttons.shortcuts')}
            </Button>
          </Tooltip>
          <Button size="sm" variant="ghost" leftIcon={<FiRefreshCw />} onClick={() => refetch()}>
            {t('common:refresh')}
          </Button>
        </HStack>
      </Flex>

      <ReviewTabs
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        unreviewedCount={unreviewedCount}
        totalCount={total}
        confirmedCount={confirmedCount}
        clearedCount={clearedCount}
      />

      <Card flexShrink={0} bg={cardBg} borderWidth={1} borderColor={borderColor}>
        <CardBody py={3}>
          <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
            <VStack align="start" spacing={0}>
              <Text fontSize="md" fontWeight="bold">{t('review:reviewProgress')}</Text>
              <Text fontSize="sm" color={mutedTextColor}>
                {t('review:pairsReviewed', { reviewed: confirmedCount + clearedCount, total: total })}
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
            value={total > 0 ? ((confirmedCount + clearedCount) / total) * 100 : 0}
            w="100%"
            colorScheme={(confirmedCount + clearedCount) >= total ? 'green' : 'red'}
            size="sm"
            borderRadius="full"
            mt={2}
          />
          <HStack mt={3} spacing={2} flexWrap="wrap">
            <Select
              size="sm"
              w={{ base: 'full', md: '200px' }}
              value={assignmentId || ''}
              onChange={(e) => {
                const params = new URLSearchParams(searchParams);
                if (e.target.value) params.set('assignment_id', e.target.value);
                else params.delete('assignment_id');
                setSearchParams(params);
              }}
              placeholder="All assignments"
            >
              {assignments.map((a: any) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
            <Button leftIcon={<FiZap />} colorScheme="orange" size="sm" onClick={onBulkOpen}>
              {t('review:bulkConfirm')}
            </Button>
            <Button leftIcon={<FiZap />} colorScheme="green" variant="outline" size="sm" onClick={onBulkClearOpen}>
              {t('review:bulkClear')}
            </Button>
          </HStack>
        </CardBody>
      </Card>

      <HStack spacing={2} wrap="wrap">
        <InputGroup size="sm" maxW={{ base: 'full', md: '200px' }}>
          <Input
            placeholder="Search files..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
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
          <option value={25}>25</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </Select>
      </HStack>

      {selected.size > 0 && (
        <HStack p={3} bg="brand.50" borderRadius="md">
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
        ) : currentItems.length === 0 ? (
          <Flex justify="center" py={8} flexDirection="column" align="center">
            <Icon as={FiCheckCircle} boxSize={12} color="green.300" mb={4} />
            <Text color="gray.500" fontSize="lg">
              {activeTab === 0 ? t('review:noPairsToReview') : t('review:noPairsFound')}
            </Text>
          </Flex>
        ) : (
          <VStack spacing={2} align="stretch">
            {currentItems.map((pair, idx) => (
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

      <ReviewSlideOver
        isOpen={slideOverOpen}
        onClose={() => setSlideOverOpen(false)}
        pairs={pairList}
        initialIndex={selectedIndex}
        onActionComplete={handleSlideOverAction}
      />

      <AlertDialog isOpen={isHelpOpen} leastDestructiveRef={cancelRef} onClose={onHelpClose}>
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader>{t('common:keyboardShortcuts')}</AlertDialogHeader>
            <AlertDialogBody>
              <VStack align="stretch" spacing={2}>
                <HStack justify="space-between"><Text fontWeight="medium">↓ / J</Text><Text color={mutedTextColor}>{t('common:keyboardShortcuts.nextPair')}</Text></HStack>
                <HStack justify="space-between"><Text fontWeight="medium">↑ / K</Text><Text color={mutedTextColor}>{t('common:keyboardShortcuts.previousPair')}</Text></HStack>
                <HStack justify="space-between"><Text fontWeight="medium">Enter</Text><Text color={mutedTextColor}>{t('common:keyboardShortcuts.viewSelectedPair')}</Text></HStack>
                <HStack justify="space-between"><Text fontWeight="medium">C</Text><Text color={mutedTextColor}>{t('common:keyboardShortcuts.confirmPlagiarism')}</Text></HStack>
                <HStack justify="space-between"><Text fontWeight="medium">X</Text><Text color={mutedTextColor}>{t('common:keyboardShortcuts.clearPair')}</Text></HStack>
              </VStack>
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button onClick={onHelpClose}>{t('common:close')}</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <AlertDialog isOpen={isBulkOpen} leastDestructiveRef={cancelRef} onClose={onBulkClose}>
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">{t('review:bulkConfirmPairs')}</AlertDialogHeader>
            <AlertDialogBody>
              <VStack align="stretch" spacing={4}>
                <Text>{t('review:bulkConfirmDescription')}</Text>
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
              <Button ref={cancelRef} onClick={onBulkClose}>{t('common:cancel')}</Button>
              <Button colorScheme="orange" onClick={handleBulkConfirm} ml={3}>{t('review:confirmAll')}</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <AlertDialog isOpen={isBulkClearOpen} leastDestructiveRef={cancelRef} onClose={onBulkClearClose}>
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">{t('review:bulkClearPairs')}</AlertDialogHeader>
            <AlertDialogBody>
              <VStack align="stretch" spacing={4}>
                <Text>{t('review:bulkClearDescription')}</Text>
                <InputGroup>
                  <Input
                    placeholder={t('review:thresholdPlaceholder')}
                    value={bulkClearThreshold}
                    onChange={(e) => setBulkClearThreshold(e.target.value)}
                  />
                  <InputRightElement>
                    <Text fontSize="sm" color={mutedTextColor} mr={2}>
                      {bulkClearThreshold ? (parseFloat(bulkClearThreshold) * 100).toFixed(0) : 0}%
                    </Text>
                  </InputRightElement>
                </InputGroup>
                <Text fontSize="xs" color="green.600">{t('review:bulkClearNote')}</Text>
              </VStack>
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkClearClose}>{t('common:cancel')}</Button>
              <Button colorScheme="green" onClick={handleBulkClear} isLoading={bulkClearMutation.isPending} ml={3}>{t('review:clearAll')}</Button>
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
  const simColor = getSimilarityColor(pair.ast_similarity);

  return (
    <Flex
      p={3}
      bg={cardBg}
      borderRadius="md"
      borderWidth={1}
      borderColor={isSelected ? 'brand.300' : 'gray.200'}
      align="center"
      gap={3}
      cursor="pointer"
      _hover={{ bg: 'gray.50', shadow: 'sm' }}
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