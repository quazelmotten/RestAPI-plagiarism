import React, { useState, useEffect, useCallback } from 'react';
import {
  VStack,
  Card,
  CardBody,
  Text,
  Button,
  useToast,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  HStack,
  Badge,
  IconButton,
  Tooltip,
  Flex,
  Progress,
  Spinner,
  Input,
  InputGroup,
  InputRightElement,
  useColorModeValue,
} from '@chakra-ui/react';
import { FiZap, FiDownload, FiRefreshCw, FiChevronLeft, FiChevronRight, FiHelpCircle, FiCheckCircle } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../../services/api';
import type { ReviewQueueResponse, PlagiarismResult, BulkConfirmResponse, ReviewStatusSummary } from '../../types';
import { useExportReview, useReviewStatus, usePairsByStatus, useBulkClear } from '../../hooks/useGrading';
import { usePagination } from '../../hooks/usePagination';
import { ReviewTabs } from './ReviewTabs';
import { ReviewToolbar } from './ReviewToolbar';
import { ReviewList } from './ReviewList';

interface ReviewQueueProps {
  assignmentId: string;
  onReviewPair: (pair: PlagiarismResult, allPairs?: PlagiarismResult[]) => void;
}

const PAGE_SIZE = 50;
const MAX_LIMIT = 500;

export const ReviewQueue: React.FC<ReviewQueueProps> = ({ assignmentId, onReviewPair }) => {
  const { t } = useTranslation(['common', 'review']);
  const toast = useToast();

  // Tab state
  const [activeTab, setActiveTab] = useState(0);

  // Filter state
  const [searchFilter, setSearchFilter] = useState('');
  const [similarityFilter, setSimilarityFilter] = useState('');
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Queue data for "To Review" tab
  const [queueData, setQueueData] = useState<ReviewQueueResponse | null>(null);
  const [queueLoading, setQueueLoading] = useState(true);

  // Bulk action state
  const [bulkThreshold, setBulkThreshold] = useState('0.8');
  const [bulkClearThreshold, setBulkClearThreshold] = useState('0');

  // Dialogs
  const { isOpen: isBulkOpen, onOpen: onBulkOpen, onClose: onBulkClose } = useDisclosure();
  const { isOpen: isBulkClearOpen, onOpen: onBulkClearOpen, onClose: onBulkClearClose } = useDisclosure();
  const { isOpen: isHelpOpen, onOpen: onHelpOpen, onClose: onHelpClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  // Mutations
  const bulkClearMutation = useBulkClear();
  const exportReview = useExportReview();

  // Colors for dark mode
  const mutedTextColor = useColorModeValue("gray.500", "gray.400");
  const inputRightElementColor = useColorModeValue("gray.500", "gray.400");

  // Fetch review status
  const { data: reviewStatus, isLoading: statusLoading, refetch: refetchStatus } = useReviewStatus(assignmentId);

  // Determine current tab status and get appropriate data
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

  // Use pagination hook for the current status
  const totalForTab = activeTab === 0 
    ? (reviewStatus?.unreviewed ?? 0)
    : activeTab === 1 
      ? (reviewStatus?.total_pairs ?? 0)
      : activeTab === 2 
        ? (reviewStatus?.confirmed ?? 0)
        : activeTab === 3 
          ? (reviewStatus?.bulk_confirmed ?? 0)
          : (reviewStatus?.cleared ?? 0);

  const pagination = usePagination({ 
    total: totalForTab, 
    pageSize,
    initialPage: 0
  });

  // Fetch pairs based on status and pagination
  const { data: pairsData, isLoading: pairsLoading, refetch: refetchPairs } = usePairsByStatus(
    assignmentId,
    getCurrentStatus(),
    Math.min(pageSize, MAX_LIMIT),
    pagination.start
  );

  // Fetch queue for "To Review" tab (separate endpoint)
  const fetchQueue = useCallback(async () => {
    if (activeTab !== 0) return;

    setQueueLoading(true);
    try {
      const response = await api.get<ReviewQueueResponse>(
        API_ENDPOINTS.REVIEW_QUEUE(assignmentId),
        { params: { limit: Math.min(pageSize, MAX_LIMIT), offset: pagination.start } }
      );
      setQueueData(response.data);
      setSelectedIndex(0);
    } catch (error) {
      toast({
        title: t('common:toasts.failedToFetchQueue'),
        status: 'error',
        duration: 3000,
      });
    } finally {
      setQueueLoading(false);
    }
  }, [assignmentId, activeTab, pageSize, pagination.start, toast]);

  // Refetch when tab or pagination changes
  useEffect(() => {
    if (activeTab === 0) {
      fetchQueue();
    } else {
      refetchPairs();
    }
  }, [activeTab, pagination.start, pageSize, fetchQueue, refetchPairs]);

  // Apply search filter locally
  const filterBySearch = useCallback((items: PlagiarismResult[]) => {
    if (!searchFilter.trim()) return items;
    const q = searchFilter.toLowerCase();
    return items.filter(item => 
      (item.file_a?.filename || '').toLowerCase().includes(q) || 
      (item.file_b?.filename || '').toLowerCase().includes(q)
    );
  }, [searchFilter]);

  // Apply similarity filter locally
  const filterBySimilarity = useCallback((items: PlagiarismResult[]) => {
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

  // Get current page items
  const getCurrentItems = useCallback((): PlagiarismResult[] => {
    if (activeTab === 0) {
      let items = queueData?.queue || [];
      items = filterBySearch(items);
      items = filterBySimilarity(items);
      return items;
    } else {
      let items = pairsData?.items || [];
      items = filterBySearch(items);
      items = filterBySimilarity(items);
      return items;
    }
  }, [activeTab, queueData, pairsData, filterBySearch, filterBySimilarity]);

  const currentItems = getCurrentItems();
  const isLoading = activeTab === 0 ? queueLoading : pairsLoading;
  const isComplete = reviewStatus ? reviewStatus.unreviewed === 0 : false;

  // Handlers
  const handleBulkConfirm = async () => {
    const threshold = parseFloat(bulkThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({ title: t('common:toasts.invalidThreshold'), description: t('common:toasts.thresholdRange'), status: 'error', duration: 3000 });
      return;
    }

    try {
      const response = await api.post<BulkConfirmResponse>(
        API_ENDPOINTS.BULK_CONFIRM(assignmentId),
        null,
        { params: { threshold } }
      );
      toast({ title: t('common:toasts.bulkConfirmComplete'), description: t('common:toasts.pairsConfirmed', { count: response.data.confirmed_pairs }), status: 'success', duration: 5000 });
      onBulkClose();
      refetchStatus();
      refetchPairs();
    } catch (error) {
      toast({ title: t('common:toasts.failedToBulkConfirm'), status: 'error', duration: 3000 });
    }
  };

  const handleBulkClear = async () => {
    const threshold = parseFloat(bulkClearThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({ title: t('common:toasts.invalidThreshold'), description: t('common:toasts.thresholdRange'), status: 'error', duration: 3000 });
      return;
    }

    try {
      const response = await bulkClearMutation.mutateAsync({ assignmentId, threshold });
      toast({ title: t('common:toasts.bulkClearComplete'), description: t('common:toasts.pairsCleared', { count: response.confirmed_pairs }), status: 'success', duration: 5000 });
      onBulkClearClose();
      refetchStatus();
      if (activeTab === 0) {
        fetchQueue();
      } else {
        refetchPairs();
      }
    } catch (error) {
      toast({ title: t('common:toasts.failedToBulkClear'), status: 'error', duration: 3000 });
    }
  };

  const handleClearAll = async () => {
    if (!confirm(t('review:confirmClearAll'))) return;
    try {
      await bulkClearMutation.mutateAsync({ assignmentId, threshold: 0 });
      toast({ title: t('review:clearAllSuccess'), status: 'success', duration: 3000 });
      refetchStatus();
      if (activeTab === 0) {
        fetchQueue();
      } else {
        refetchPairs();
      }
    } catch (error) {
      toast({ title: t('review:clearAllError'), status: 'error', duration: 3000 });
    }
  };

  const handleExport = async () => {
    try {
      const threshold = similarityFilter === 'all' ? 0.3 : parseFloat(similarityFilter) || 0.3;
      const result = await exportReview.mutateAsync({ assignmentId, threshold });
      const blob = new Blob([result.html_content], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = result.filename;
      link.click();
      URL.revokeObjectURL(url);
      toast({ title: t('common:toasts.exportComplete'), description: t('common:toasts.htmlReportDownloaded'), status: 'success', duration: 3000 });
    } catch (error) {
      toast({ title: t('common:toasts.exportFailed'), description: t('common:toasts.failedToGenerateHtml'), status: 'error', duration: 3000 });
    }
  };

  const handleSelectItem = (item: PlagiarismResult, index: number) => {
    setSelectedIndex(index);
    onReviewPair(item, currentItems);
  };

  const handleItemAction = async (item: PlagiarismResult) => {
    if (!item.id) {
      toast({ title: t('common:errors.generic'), description: t('common:toasts.pairIdMissing'), status: 'error', duration: 3000 });
      return;
    }
    try {
      await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(item.id));
      toast({ title: t('common:toasts.confirmed'), description: t('common:toasts.pairMarkedAsPlagiarism'), status: 'success', duration: 1500 });
      refetchStatus();
      refetchPairs();
    } catch (error) {
      toast({ title: t('common:errors.generic'), description: t('common:toasts.failedToConfirm'), status: 'error', duration: 3000 });
    }
  };

  const handlePrevItem = () => {
    if (selectedIndex > 0) {
      const newIndex = selectedIndex - 1;
      setSelectedIndex(newIndex);
      onReviewPair(currentItems[newIndex], currentItems);
    }
  };

  const handleNextItem = () => {
    if (selectedIndex < currentItems.length - 1) {
      const newIndex = selectedIndex + 1;
      setSelectedIndex(newIndex);
      onReviewPair(currentItems[newIndex], currentItems);
    }
  };

  // Computed values
  const reviewedPairs = (reviewStatus?.confirmed || 0) + (reviewStatus?.bulk_confirmed || 0) + (reviewStatus?.cleared || 0);
  const totalPairs = reviewStatus?.total_pairs || 0;
  const progress = totalPairs > 0 ? (reviewedPairs / totalPairs) * 100 : 0;
  const confirmedFiles = queueData?.confirmed_files ?? 0;
  const totalFiles = queueData?.total_files ?? 0;

  return (
    <VStack align="stretch" spacing={4} h="100%" minH={0}>
      {/* Tabs */}
      <ReviewTabs
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        unreviewedCount={reviewStatus?.unreviewed || 0}
        totalCount={reviewStatus?.total_pairs || 0}
        confirmedCount={reviewStatus?.confirmed || 0}
        bulkConfirmedCount={reviewStatus?.bulk_confirmed || 0}
        clearedCount={reviewStatus?.cleared || 0}
      />

      {/* Progress Header - only show for To Review tab */}
      {activeTab === 0 && reviewStatus && (
        <Card flexShrink={0}>
          <CardBody>
            <Flex justify="space-between" align="flex-start" mb={3} wrap="wrap" gap={3}>
              <VStack align="start" spacing={0}>
                <HStack>
                  <Text fontSize="lg" fontWeight="bold">{t('review:reviewProgress')}</Text>
                  <Tooltip label={t('review:keyboardShortcuts')}>
                    <Button size="sm" variant="ghost" onClick={onHelpOpen}>{t('common:buttons.shortcuts')}</Button>
                  </Tooltip>
                </HStack>
                <Text fontSize="sm" color={mutedTextColor}>
                  {t('review:pairsReviewed', { reviewed: reviewedPairs, total: totalPairs })}
                </Text>
              </VStack>
              <HStack spacing={2} flexWrap="wrap">
                <Badge colorScheme="blue" fontSize="md" px={3} py={1}>
                  {reviewStatus.unreviewed} {t('review:unreviewed')}
                </Badge>
                {isComplete && (
                  <Badge colorScheme="green" fontSize="md" px={3} py={1}>
                    {t('review:complete')}
                  </Badge>
                )}
              </HStack>
            </Flex>
            <Progress 
              value={progress} 
              w="100%" 
              colorScheme={progress >= 100 ? 'green' : progress >= 50 ? 'orange' : 'red'}
              size="sm"
              borderRadius="full"
              mt={2}
            />
            <HStack spacing={3}>
              <Text fontSize="sm" color={mutedTextColor}>
                {t('review:filesConfirmed', { confirmed: confirmedFiles, total: totalFiles })}
              </Text>
            </HStack>

            {/* Action Buttons */}
            <HStack mt={4} spacing={2} flexWrap="wrap">
              {!isComplete && (
                <>
                  <Button leftIcon={<FiZap />} colorScheme="orange" onClick={onBulkOpen} size="sm">
                    {t('review:bulkConfirm')}
                  </Button>
                  <Button leftIcon={<FiZap />} colorScheme="green" variant="outline" onClick={onBulkClearOpen} size="sm">
                    {t('review:bulkClear')}
                  </Button>
                  <Button leftIcon={<FiCheckCircle />} colorScheme="blue" variant="outline" onClick={handleClearAll} size="sm" isLoading={bulkClearMutation.isPending}>
                    {t('review:clearAllAndFinish')}
                  </Button>
                </>
              )}
              <Button leftIcon={<FiDownload />} variant="outline" onClick={handleExport} size="sm" isLoading={exportReview.isPending}>
                {t('review:exportHtml')}
              </Button>
              <Button leftIcon={<FiRefreshCw />} variant="ghost" onClick={() => { refetchStatus(); fetchQueue(); }} size="sm">
                {t('common:refresh')}
              </Button>
            </HStack>
          </CardBody>
        </Card>
      )}

      {/* Toolbar */}
      <ReviewToolbar
        searchFilter={searchFilter}
        setSearchFilter={setSearchFilter}
        similarityFilter={similarityFilter}
        setSimilarityFilter={setSimilarityFilter}
        pageSize={pageSize}
        setPageSize={setPageSize}
        showingStart={pagination.start + 1}
        showingEnd={pagination.end}
        total={totalForTab}
        page={pagination.page}
        totalPages={pagination.totalPages}
        onPrevPage={pagination.prevPage}
        onNextPage={pagination.nextPage}
        isFirstPage={pagination.isFirstPage}
        isLastPage={pagination.isLastPage}
      />

      {/* Pairs List */}
      <ReviewList
        items={currentItems}
        isLoading={isLoading}
        isEmpty={currentItems.length === 0}
        isEmptyMessage={activeTab === 0 ? (isComplete ? t('review:allFilesReviewed') : t('review:noPairsToReview')) : t('review:noPairsFound')}
        selectedIndex={selectedIndex}
        onSelectItem={handleSelectItem}
        onAction={handleItemAction}
      />

      {/* Keyboard Shortcuts Help Dialog */}
      <AlertDialog isOpen={isHelpOpen} onClose={onHelpClose} leastDestructiveRef={cancelRef}>
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

      {/* Bulk Confirm Dialog */}
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

      {/* Bulk Clear Dialog */}
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

export default ReviewQueue;