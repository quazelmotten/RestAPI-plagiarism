import React, { useMemo, memo, useState } from 'react';
import { Card, CardBody, HStack, Text, Badge, VStack, Box, useColorModeValue, Button, IconButton, Input, Skeleton, Tooltip } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiChevronLeft, FiChevronRight, FiChevronsLeft, FiChevronsRight, FiCopy, FiCheck } from 'react-icons/fi';
import { useCopyToClipboard } from '../../hooks/useCopyToClipboard';
import type { PlagiarismResult } from '../../types';

interface ResultsListProps {
  results: PlagiarismResult[];
  totalPairs: number;
  borderColor: string;
  hoverBg: string;
  getSimilarityColor: (similarity: number) => string;
  handleCompare: (result: PlagiarismResult) => void;
  cardBg?: string;
  loading?: boolean;
}

const ResultRow = memo<{
  result: PlagiarismResult;
  borderColor: string;
  hoverBg: string;
  getSimilarityColor: (similarity: number) => string;
  handleCompare: (result: PlagiarismResult) => void;
  t: (key: string, options?: { count?: number; total?: number }) => string;
}>(({ result, borderColor, hoverBg, getSimilarityColor, handleCompare, t }) => (
  <HStack
    p={3}
    borderWidth={1}
    borderColor={borderColor}
    borderRadius="md"
    cursor="pointer"
    _hover={{ bg: hoverBg }}
    onClick={() => handleCompare(result)}
    justify="space-between"
    align="center"
  >
    <HStack flex={1} spacing={2} align="center">
      <VStack align="start" spacing={0}>
        <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="200px">
          {result.file_a.filename}
        </Text>
        {result.file_a.task_id && (
          <Text fontSize="xs" color="gray.500" noOfLines={1} maxW="120px">
            ({result.file_a.task_id.substring(0, 8)}...)
          </Text>
        )}
      </VStack>
      <Text fontSize="sm" color="gray.500" fontWeight="medium">{t('common:vs')}</Text>
      <VStack align="start" spacing={0}>
        <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="200px">
          {result.file_b.filename}
        </Text>
        {result.file_b.task_id && (
          <Text fontSize="xs" color="gray.500" noOfLines={1} maxW="120px">
            ({result.file_b.task_id.substring(0, 8)}...)
          </Text>
        )}
      </VStack>
    </HStack>
    <Badge
      colorScheme={getSimilarityColor(result.ast_similarity || 0)}
      fontSize="md"
      px={3}
      py={1}
      ml={4}
    >
      {((result.ast_similarity || 0) * 100).toFixed(1)}%
    </Badge>
  </HStack>
));

ResultRow.displayName = 'ResultRow';

const RESULTS_PER_PAGE = 20;

const ResultsList: React.FC<ResultsListProps & { loading?: boolean }> = ({
  results,
  totalPairs,
  borderColor,
  hoverBg,
  getSimilarityColor,
  handleCompare,
  cardBg,
  loading = false,
}) => {
  const { t } = useTranslation(['results', 'common']);
  const listNoticeBg = useColorModeValue('gray.50', 'gray.700');
  const listNoticeColor = useColorModeValue('gray.600', 'gray.400');
  const [page, setPage] = useState(0);
  const [goPage, setGoPage] = useState('');

  const totalPages = Math.max(1, Math.ceil(results.length / RESULTS_PER_PAGE));
  const paginatedResults = results.slice(page * RESULTS_PER_PAGE, (page + 1) * RESULTS_PER_PAGE);

  const handleGoPage = () => {
    const pageNum = parseInt(goPage, 10) - 1;
    if (!isNaN(pageNum) && pageNum >= 0 && pageNum < totalPages) {
      setPage(pageNum);
      setGoPage('');
    }
  };

  return (
    <Card bg={cardBg}>
      <CardBody>
        <HStack justify="space-between" align="center" mb={4}>
          <Text fontSize="md" fontWeight="bold">{t('resultsList.topSimilarities')}</Text>
           <HStack spacing={2}>
             <Text color="gray.500" fontSize="sm">
               {t('resultsList.showing', { count: paginatedResults.length, total: totalPairs })}
             </Text>
           </HStack>
        </HStack>

        <VStack align="stretch" spacing={2} mb={4}>
          {loading ? (
            Array.from({ length: Math.min(RESULTS_PER_PAGE, 5) }).map((_, i) => (
              <Skeleton key={i} height="60px" borderRadius="md" />
            ))
          ) : (
            paginatedResults.map((result) => (
              <ResultRow
                key={`${result.file_a.id}-${result.file_b.id}`}
                result={result}
                borderColor={borderColor}
                hoverBg={hoverBg}
                getSimilarityColor={getSimilarityColor}
                handleCompare={handleCompare}
                t={t}
              />
            ))
          )}
        </VStack>

        {totalPages > 1 && (
          <HStack justify="center" spacing={2} pt={2} borderTopWidth={1} borderColor={borderColor}>
            <IconButton
              size="sm"
              icon={<FiChevronsLeft />}
              onClick={() => setPage(0)}
              isDisabled={page === 0}
              aria-label="First page"
            />
            <IconButton
              size="sm"
              icon={<FiChevronLeft />}
              onClick={() => setPage(p => Math.max(0, p - 1))}
              isDisabled={page === 0}
              aria-label="Previous page"
            />
            <Text fontSize="sm" minW="80px" textAlign="center">
              Page {page + 1} / {totalPages}
            </Text>
            <IconButton
              size="sm"
              icon={<FiChevronRight />}
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              isDisabled={page >= totalPages - 1}
              aria-label="Next page"
            />
            <IconButton
              size="sm"
              icon={<FiChevronsRight />}
              onClick={() => setPage(totalPages - 1)}
              isDisabled={page >= totalPages - 1}
              aria-label="Last page"
            />
            <HStack spacing={1} ml={2}>
              <Input
                size="xs"
                w="60px"
                placeholder="Go to..."
                value={goPage}
                onChange={(e) => setGoPage(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleGoPage(); }}
              />
              <Button size="xs" onClick={handleGoPage} isDisabled={!goPage}>
                Go
              </Button>
            </HStack>
          </HStack>
        )}
      </CardBody>
    </Card>
  );
};

export default ResultsList;
