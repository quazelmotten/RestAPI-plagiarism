import React, { useState, useEffect, useCallback } from 'react';
import {
  VStack, HStack, Card, CardBody, Text, Badge, Button,
  Input, InputGroup, InputRightElement, Progress, Spinner,
  useToast, AlertDialog, AlertDialogBody, AlertDialogFooter,
  AlertDialogHeader, AlertDialogContent, AlertDialogOverlay,
  useDisclosure, Select, Box, Flex, IconButton, Tooltip, Tabs, TabList, Tab
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiZap, FiFilter, FiDownload, FiRefreshCw, FiChevronLeft, FiChevronRight, FiHelpCircle, FiCheckCircle, FiAlertTriangle, FiLayers } from 'react-icons/fi';
import { FaFilter } from 'react-icons/fa';
import api, { API_ENDPOINTS } from '../../services/api';
import type { ReviewQueueResponse, PlagiarismResult, BulkConfirmResponse, ReviewStatusSummary } from '../../types';
import ReviewQueueItem from './ReviewQueueItem';
import { useExportReview, useReviewStatus, usePairsByStatus, useBulkClear } from '../../hooks/useGrading';

interface ReviewQueueProps {
  assignmentId: string;
  onReviewPair: (pair: PlagiarismResult, allPairs?: PlagiarismResult[]) => void;
}

const ReviewQueue: React.FC<ReviewQueueProps> = ({ assignmentId, onReviewPair }) => {
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [bulkThreshold, setBulkThreshold] = useState('0.8');
  const [bulkLoading, setBulkLoading] = useState(false);
  const toast = useToast();
  const { isOpen: isBulkOpen, onOpen: onBulkOpen, onClose: onBulkClose } = useDisclosure();
  const { isOpen: isBulkClearOpen, onOpen: onBulkClearOpen, onClose: onBulkClearClose } = useDisclosure();
  const { isOpen: isHelpOpen, onOpen: onHelpOpen, onClose: onHelpClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const { t } = useTranslation(['common', 'review']);

  const bulkClearMutation = useBulkClear();
  const [bulkClearThreshold, setBulkClearThreshold] = useState('0');

  // Tabs
  const [activeTab, setActiveTab] = useState<number>(0);

  // Filters
  const [similarityFilter, setSimilarityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  const exportReview = useExportReview();
  const { data: reviewStatus, isLoading: statusLoading, refetch: refetchStatus } = useReviewStatus(assignmentId);
  const { data: pairsData, isLoading: pairsLoading, refetch: refetchPairs } = usePairsByStatus(
    assignmentId,
    activeTab === 0 ? 'unreviewed' : activeTab === 1 ? 'all' : activeTab === 2 ? 'plagiarism' : activeTab === 3 ? 'bulk_confirmed' : 'clear',
    100,
    0
  );

  const handleStatusRefresh = useCallback(() => {
    refetchStatus();
    refetchPairs();
  }, [refetchStatus, refetchPairs]);

  useEffect(() => {
    fetchQueue();
  }, [assignmentId]);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const response = await api.get<ReviewQueueResponse>(
        API_ENDPOINTS.REVIEW_QUEUE(assignmentId)
      );
      setQueue(response.data);
      setSelectedIndex(0);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to fetch review queue',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchAllPairs = async () => {
    setLoading(true);
    try {
      const response = await api.get<{ items: PlagiarismResult[]; total: number }>(
        API_ENDPOINTS.PAIRS_BY_STATUS(assignmentId, 'all', 100, 0)
      );
      return response.data.items;
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to fetch pairs',
        status: 'error',
        duration: 3000,
      });
      return [];
    } finally {
      setLoading(false);
    }
  };

  const handleBulkConfirm = async () => {
    const threshold = parseFloat(bulkThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({
        title: 'Invalid threshold',
        description: 'Please enter a value between 0 and 1',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setBulkLoading(true);
    try {
      const response = await api.post<BulkConfirmResponse>(
        API_ENDPOINTS.BULK_CONFIRM(assignmentId),
        null,
        { params: { threshold } }
      );

      toast({
        title: 'Bulk Confirm Complete',
        description: `Confirmed ${response.data.confirmed_pairs} pairs, ${response.data.confirmed_files} files`,
        status: 'success',
        duration: 5000,
      });

      onBulkClose();
      await fetchQueue();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to bulk confirm',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkClear = async () => {
    const threshold = parseFloat(bulkClearThreshold);
    if (isNaN(threshold) || threshold < 0 || threshold > 1) {
      toast({
        title: 'Invalid threshold',
        description: 'Please enter a value between 0 and 1',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    try {
      const response = await bulkClearMutation.mutateAsync({
        assignmentId,
        threshold,
      });

      toast({
        title: 'Bulk Clear Complete',
        description: `Cleared ${response.confirmed_pairs} pairs`,
        status: 'success',
        duration: 5000,
      });

      onBulkClearClose();
      await fetchQueue();
      handleStatusRefresh();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to bulk clear',
        status: 'error',
        duration: 3000,
      });
    }
  };

  const handleExport = async () => {
    try {
      const threshold = similarityFilter === 'all' ? 0.3 : parseFloat(similarityFilter);
      const result = await exportReview.mutateAsync({ assignmentId, threshold });

      const blob = new Blob([result.html_content], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = result.filename;
      link.click();
      URL.revokeObjectURL(url);

      toast({
        title: 'Export Complete',
        description: 'HTML report downloaded',
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Export Failed',
        description: 'Failed to generate HTML report',
        status: 'error',
        duration: 3000,
      });
    }
  };

  const handleItemAction = async (resultId?: string, action?: 'confirm' | 'clear') => {
    // If action provided (from keyboard), perform it directly
    if (resultId && action) {
      try {
        if (action === 'confirm') {
          await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(resultId));
          toast({
            title: 'Confirmed',
            description: 'Pair marked as plagiarism',
            status: 'success',
            duration: 1500,
          });
        } else {
          await api.post(API_ENDPOINTS.CLEAR_PAIR(resultId));
          toast({
            title: 'Cleared',
            description: 'Pair marked as not plagiarism',
            status: 'info',
            duration: 1500,
          });
        }
      } catch (error) {
        toast({
          title: 'Error',
          description: `Failed to ${action}`,
          status: 'error',
          duration: 3000,
        });
        return;
      }
    }
    
    // Refresh queue
    const newQueue = await fetchQueueOnce();
    handleStatusRefresh();
    
    // Auto-advance to next pair if we have more items
    if (newQueue && newQueue.queue.length > 0 && selectedIndex < newQueue.queue.length - 1) {
      setSelectedIndex(prev => prev + 1);
      toast({
        title: 'Next pair',
        description: `Jumped to pair ${selectedIndex + 2}`,
        status: 'success',
        duration: 1000,
      });
    } else if (newQueue && newQueue.queue.length > 0) {
      toast({
        title: 'No more pairs',
        description: 'This was the last pair in queue',
        status: 'info',
        duration: 2000,
      });
    }
  };

  // Separate fetch function that returns the new queue
  const fetchQueueOnce = async (): Promise<ReviewQueueResponse | null> => {
    try {
      const response = await api.get<ReviewQueueResponse>(
        API_ENDPOINTS.REVIEW_QUEUE(assignmentId)
      );
      setQueue(response.data);
      return response.data;
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to fetch review queue',
        status: 'error',
        duration: 3000,
      });
      return null;
    }
  };

  // Apply filters - must be defined before handleKeyDown
  const filteredQueue = React.useMemo(() => {
    if (!queue) return [];
    let items = queue.queue;

    // Similarity filter
    if (similarityFilter !== 'all') {
      const threshold = parseFloat(similarityFilter);
      items = items.filter(item => (item.ast_similarity || 0) >= threshold);
    }

    return items;
  }, [queue, similarityFilter]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!queue || queue.queue.length === 0) return;

    // Ignore if typing in input
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

    const items = filteredQueue;
    switch (e.key.toLowerCase()) {
      case 'arrowdown':
      case 'j':
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, items.length - 1));
        break;
      case 'arrowup':
      case 'k':
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'enter':
        e.preventDefault();
        if (items[selectedIndex]) {
          onReviewPair(items[selectedIndex], items);
        }
        break;
      case 'c':
        // Confirm plagiarism - find the current item and trigger confirm
        e.preventDefault();
        if (items[selectedIndex]?.id) {
          handleItemAction(items[selectedIndex].id, 'confirm');
        }
        break;
      case 'x':
        // Clear pair - find the current item and trigger clear
        e.preventDefault();
        if (items[selectedIndex]?.id) {
          handleItemAction(items[selectedIndex].id, 'clear');
        }
        break;
    }
  }, [queue, selectedIndex, onReviewPair, filteredQueue]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (loading) return <Spinner size="lg" />;
  if (!queue && !reviewStatus) return null;

  const reviewedPairs = (reviewStatus?.confirmed || 0) + (reviewStatus?.bulk_confirmed || 0) + (reviewStatus?.cleared || 0);
  const totalPairs = reviewStatus?.total_pairs || 0;
  const progress = totalPairs > 0 ? (reviewedPairs / totalPairs) * 100 : 0;
  const isComplete = reviewStatus ? reviewStatus.unreviewed === 0 : false;

  return (
    <VStack align="stretch" spacing={4}>
      {/* Tabs */}
      <Card>
        <CardBody py={2}>
          <Tabs variant="soft-rounded" colorScheme="blue" onChange={setActiveTab}>
            <TabList>
              <Tab>{t('review:toReview')} ({reviewStatus?.unreviewed || 0})</Tab>
              <Tab>{t('review:allPairs')} ({reviewStatus?.total_pairs || 0})</Tab>
              <Tab>{t('review:confirmed')} ({reviewStatus?.confirmed || 0})</Tab>
              <Tab>{t('review:bulkConfirmed')} ({reviewStatus?.bulk_confirmed || 0})</Tab>
              <Tab>{t('review:cleared')} ({reviewStatus?.cleared || 0})</Tab>
            </TabList>
          </Tabs>
        </CardBody>
      </Card>

      {/* Progress Header */}
      {activeTab === 0 && reviewStatus && (
        <Card>
          <CardBody>
            <Flex justify="space-between" align="flex-start" mb={3} wrap="wrap" gap={3}>
              <VStack align="start" spacing={0}>
                <HStack>
                  <Text fontSize="lg" fontWeight="bold">{t('review:reviewProgress')}</Text>
                  <Tooltip label={t('review:keyboardShortcuts')}>
                    <IconButton
                      aria-label="Help"
                      icon={<FiHelpCircle />}
                      size="sm"
                      variant="ghost"
                      onClick={onHelpOpen}
                    />
                  </Tooltip>
                </HStack>
                <Text fontSize="sm" color="gray.500">
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
            <Progress value={progress} colorScheme="blue" size="lg" />

            {/* Bulk Confirm + Bulk Clear + Export */}
            <HStack mt={4} spacing={2} flexWrap="wrap">
              {!isComplete && (
                <>
                  <Button
                    leftIcon={<FiZap />}
                    colorScheme="orange"
                    onClick={onBulkOpen}
                    size="sm"
                  >
                    {t('review:bulkConfirm')}
                  </Button>
                  <Button
                    leftIcon={<FiZap />}
                    colorScheme="green"
                    variant="outline"
                    onClick={onBulkClearOpen}
                    size="sm"
                  >
                    {t('review:bulkClear')}
                  </Button>
                </>
              )}
              <Button
                leftIcon={<FiDownload />}
                variant="outline"
                onClick={handleExport}
                size="sm"
                isLoading={exportReview.isPending}
              >
                {t('review:exportHtml')}
              </Button>
              <Button
                leftIcon={<FiRefreshCw />}
                variant="ghost"
                onClick={fetchQueue}
                size="sm"
              >
                {t('common:refresh')}
              </Button>
            </HStack>
          </CardBody>
        </Card>
      )}

      {/* Filter Toolbar */}
      <Card>
        <CardBody py={2}>
          <HStack spacing={4} flexWrap="wrap">
            <HStack spacing={2}>
              <FiFilter />
              <Text fontSize="sm" fontWeight="medium">{t('review:filters')}</Text>
            </HStack>
            <Select
              size="sm"
              w="150px"
              value={similarityFilter}
              onChange={(e) => setSimilarityFilter(e.target.value)}
            >
              <option value="all">{t('review:allSimilarity')}</option>
              <option value="0.8">≥80%</option>
              <option value="0.5">≥50%</option>
              <option value="0.3">≥30%</option>
            </Select>
             {activeTab === 0 && queue && (
               <Text fontSize="sm" color="gray.500">
                 {t('review:showingPairs', { filtered: filteredQueue.length, total: queue.queue.length })}
               </Text>
             )}
            {activeTab > 0 && pairsData && (
              <Text fontSize="sm" color="gray.500">
                {t('review:totalPairs', { total: pairsData.total })}
              </Text>
            )}
          </HStack>
        </CardBody>
      </Card>

      {/* Pairs List */}
      <Box overflowY="auto" maxH="calc(100vh - 400px)" borderWidth="1px" borderRadius="md" p={2}>
        <VStack align="stretch" spacing={2}>
        {activeTab === 0 ? (
          filteredQueue.length === 0 ? (
            <Card>
              <CardBody>
                <Text textAlign="center" color="gray.500">
                  {isComplete ? t('review:allFilesReviewed') : t('review:noPairsToReview')}
                </Text>
              </CardBody>
            </Card>
          ) : (
            filteredQueue.map((item, idx) => (
              <Box
                key={item.id || `${item.file_a.id}-${item.file_b.id}`}
                borderWidth={selectedIndex === idx ? '2px' : '1px'}
                borderColor={selectedIndex === idx ? 'brand.500' : 'gray.200'}
                borderRadius="md"
                transition="border-color 0.15s"
              >
                <ReviewQueueItem
                  item={item}
                  index={idx}
                  onReview={(pair) => onReviewPair(pair, filteredQueue)}
                  onAction={handleItemAction}
                />
              </Box>
            ))
          )
        ) : pairsLoading ? (
          <Card>
            <CardBody>
              <Spinner />
            </CardBody>
          </Card>
        ) : pairsData && pairsData.items.length > 0 ? (
          pairsData.items.map((item, idx) => (
            <Box
              key={item.id || `${item.file_a.id}-${item.file_b.id}`}
              borderWidth="1px"
              borderColor="gray.200"
              borderRadius="md"
            >
              <ReviewQueueItem
                item={item}
                index={idx}
                onReview={(pair) => onReviewPair(pair, pairsData.items)}
                onAction={async () => {
                  await Promise.all([refetchStatus(), refetchPairs()]);
                }}
              />
            </Box>
          ))
        ) : (
          <Card>
            <CardBody>
              <Text textAlign="center" color="gray.500">
                No pairs found
              </Text>
            </CardBody>
          </Card>
        )}
        </VStack>
      </Box>

      {/* Navigation */}
      {filteredQueue.length > 0 && (
        <HStack justify="center" spacing={2}>
          <IconButton
            aria-label="Previous"
            icon={<FiChevronLeft />}
            onClick={() => setSelectedIndex(prev => Math.max(0, prev - 1))}
            isDisabled={selectedIndex === 0}
          />
          <Text fontSize="sm">
            {selectedIndex + 1} / {filteredQueue.length}
          </Text>
          <IconButton
            aria-label="Next"
            icon={<FiChevronRight />}
            onClick={() => setSelectedIndex(prev => Math.min(filteredQueue.length - 1, prev + 1))}
            isDisabled={selectedIndex >= filteredQueue.length - 1}
          />
        </HStack>
      )}

      {/* Keyboard Shortcuts Help Dialog */}
      <AlertDialog isOpen={isHelpOpen} onClose={onHelpClose} leastDestructiveRef={cancelRef}>
        <AlertDialogOverlay>
          <AlertDialogContent>
             <AlertDialogHeader>{t('common:keyboardShortcuts')}</AlertDialogHeader>
            <AlertDialogBody>
              <VStack align="stretch" spacing={2}>
                <HStack justify="space-between">
                  <Text fontWeight="medium">↓ / J</Text>
                  <Text color="gray.500">Next pair</Text>
                </HStack>
                <HStack justify="space-between">
                  <Text fontWeight="medium">↑ / K</Text>
                  <Text color="gray.500">Previous pair</Text>
                </HStack>
<HStack justify="space-between">
                    <Text fontWeight="medium">{t('common:enter')}</Text>
                    <Text color="gray.500">{t('review:viewSelectedPairShortcut')}</Text>
                  </HStack>
                  <HStack justify="space-between">
                    <Text fontWeight="medium">C</Text>
                    <Text color="gray.500">{t('review:confirmPlagiarism')}</Text>
                  </HStack>
                  <HStack justify="space-between">
                    <Text fontWeight="medium">X</Text>
                    <Text color="gray.500">{t('review:clearNoPlagiarism')}</Text>
                  </HStack>
              </VStack>
            </AlertDialogBody>
             <AlertDialogFooter>
               <Button onClick={onHelpClose}>{t('common:close')}</Button>
             </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Bulk Confirm Dialog */}
      <AlertDialog
        isOpen={isBulkOpen}
        leastDestructiveRef={cancelRef}
        onClose={onBulkClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('review:bulkConfirmPairs')}
            </AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="stretch" spacing={4}>
                <Text>
                  {t('review:bulkConfirmDescription')}
                </Text>

                <InputGroup>
                  <Input
                    placeholder={t('review:thresholdPlaceholder')}
                    value={bulkThreshold}
                    onChange={(e) => setBulkThreshold(e.target.value)}
                  />
                  <InputRightElement>
                    <Text fontSize="sm" color="gray.500" mr={2}>
                      {bulkThreshold ? (parseFloat(bulkThreshold) * 100).toFixed(0) : 0}%
                    </Text>
                  </InputRightElement>
                </InputGroup>

                <Text fontSize="xs" color="orange.500">
                  {t('review:bulkConfirmWarning')}
                </Text>
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="orange"
                onClick={handleBulkConfirm}
                isLoading={bulkLoading}
                ml={3}
              >
                {t('review:confirmAll')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Bulk Clear Dialog */}
      <AlertDialog
        isOpen={isBulkClearOpen}
        leastDestructiveRef={cancelRef}
        onClose={onBulkClearClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('review:bulkClearPairs')}
            </AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="stretch" spacing={4}>
                <Text>
                  {t('review:bulkClearDescription')}
                </Text>

                <InputGroup>
                  <Input
                    placeholder={t('review:thresholdPlaceholder')}
                    value={bulkClearThreshold}
                    onChange={(e) => setBulkClearThreshold(e.target.value)}
                  />
                  <InputRightElement>
                    <Text fontSize="sm" color="gray.500" mr={2}>
                      {bulkClearThreshold ? (parseFloat(bulkClearThreshold) * 100).toFixed(0) : 0}%
                    </Text>
                  </InputRightElement>
                </InputGroup>

                <Text fontSize="xs" color="green.600">
                  {t('review:bulkClearNote')}
                </Text>
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkClearClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="green"
                onClick={handleBulkClear}
                isLoading={bulkClearMutation.isPending}
                ml={3}
              >
                {t('review:clearAll')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
};

export default ReviewQueue;
