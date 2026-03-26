import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  Card,
  CardBody,
  Heading,
  VStack,
  HStack,
  Text,
  Box,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Tooltip,
  Spinner,
  Button,
  useColorModeValue,
} from '@chakra-ui/react';
import { FiBarChart2 } from 'react-icons/fi';
import api, { API_ENDPOINTS } from '../../services/api';
import type { PlagiarismResult } from '../../types';

interface SimilarityDistributionProps {
  results: PlagiarismResult[];
  totalPairs: number;
  cardBg?: string;
  taskId?: string;
  stats?: {
    high: number;
    medium: number;
    low: number;
    avg: number;
  };
}

interface HistogramBin {
  range: string;
  count: number;
}

// Resolution for high-res histogram fetched from backend
const HIGH_RES_BINS = 200;

const SimilarityDistribution: React.FC<SimilarityDistributionProps> = ({
  results,
  totalPairs,
  cardBg,
  taskId,
  stats,
}) => {
  const [binCount, setBinCount] = useState(25);
  const [isLogScale, setIsLogScale] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highResCounts, setHighResCounts] = useState<number[] | null>(null);

  const textColor = useColorModeValue('gray.700', 'gray.200');
  const rangeColor = useColorModeValue('gray.600', 'gray.400');
  const chartBorderColor = useColorModeValue('gray.200', 'gray.600');
  const scrollbarTrackBg = useColorModeValue('gray.100', 'gray.700');
  const scrollbarThumbBg = useColorModeValue('gray.400', 'gray.500');

  // Cache high-res histogram per task: stores raw counts array for 200 bins
  const highResCacheRef = useRef<Map<string, number[]>>(new Map());

  // Fetch high-resolution histogram (200 uniform bins) from API
  const fetchHighResHistogram = useCallback(async (tid: string) => {
    const cached = highResCacheRef.current.get(tid);
    if (cached) {
      setHighResCounts(cached);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // Request 200 bins for high resolution
      const { data } = await api.get<{ histogram: HistogramBin[]; total: number }>(
        API_ENDPOINTS.TASK_HISTOGRAM(tid, HIGH_RES_BINS)
      );
      
      // Extract raw counts from histogram bins (they're already in order)
      const rawCounts = (data.histogram || []).map(bin => bin.count);
      highResCacheRef.current.set(tid, rawCounts);
      setHighResCounts(rawCounts);
    } catch (err) {
      console.error('Failed to fetch histogram:', err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // Load high-res histogram when task changes
  useEffect(() => {
    if (taskId) {
      fetchHighResHistogram(taskId);
    } else {
      setHighResCounts(null);
    }
  }, [taskId, fetchHighResHistogram]);

  // Derive display bins by combining high-res bins
  const displayData = useMemo(() => {
    if (!taskId || !highResCounts) return [];
    
    const sourceBins = HIGH_RES_BINS;
    const targetBins = binCount;
    const combined = new Array(targetBins).fill(0);
    
    // Distribute each high-res bin into appropriate target bin
    for (let srcIdx = 0; srcIdx < sourceBins; srcIdx++) {
      const count = highResCounts[srcIdx] || 0;
      const tgtIdx = Math.floor(srcIdx * targetBins / sourceBins);
      if (tgtIdx >= 0 && tgtIdx < targetBins) {
        combined[tgtIdx] += count;
      }
    }
    
    // Generate bins with precise range labels (avoid overlap)
    return combined.map((count, i) => {
      const lower = (i / targetBins) * 100;
      const upper = ((i + 1) / targetBins) * 100;
      const formatPct = (n: number) => {
        // If it's an integer after rounding, show as integer, else one decimal
        const rounded = Math.round(n);
        if (Math.abs(n - rounded) < 0.001) {
          return `${rounded}`;
        }
        return `${n.toFixed(1)}`;
      };
      return {
        range: `${formatPct(lower)}-${formatPct(upper)}%`,
        count,
      };
    });
  }, [taskId, binCount, highResCounts]);

  // Compute max values for scaling
  const maxLinear = useMemo(() => {
    return Math.max(...displayData.map(b => b.count), 1);
  }, [displayData]);

  const maxLog = useMemo(() => {
    if (displayData.length === 0) return 1;
    const maxLogVal = Math.max(...displayData.map(b => Math.log10(b.count + 1)));
    return maxLogVal || 1;
  }, [displayData]);

  // Determine how often to show X-axis labels to avoid overlap
  const labelStep = useMemo(() => {
    if (displayData.length === 0) return 1;
    // Aim for ~30 labels max
    return Math.max(1, Math.ceil(displayData.length / 30));
  }, [displayData.length]);

  const handleBinCountChange = useCallback((value: number) => {
    setBinCount(value);
  }, []);

  const toggleLogScale = useCallback(() => {
    setIsLogScale(prev => !prev);
  }, []);

  const getBarColor = (rangeLabel: string) => {
    const midPct = parseFloat(rangeLabel.split('-')[0]) || 0;
    if (midPct < 25) return 'green.500';
    if (midPct < 50) return 'orange.500';
    return 'red.500';
  };

  const showIncompleteWarning = results.length < totalPairs && !taskId;

  return (
    <Card bg={cardBg}>
      <CardBody>
        <VStack spacing={4} align="stretch">
          <HStack justify="space-between" align="center">
            <Heading size="sm">Similarity Distribution</Heading>
            <HStack spacing={3} align="center">
              <Button
                size="sm"
                variant={isLogScale ? 'solid' : 'outline'}
                colorScheme="blue"
                leftIcon={<FiBarChart2 />}
                onClick={toggleLogScale}
                title={isLogScale ? 'Switch to linear scale' : 'Switch to log scale'}
              >
                {isLogScale ? 'Log Scale' : 'Log Scale'}
              </Button>
              <Text fontSize="xs" color="gray.500" minW="80px">
                Bins: {binCount}
              </Text>
              <Slider
                value={binCount}
                onChange={handleBinCountChange}
                min={5}
                max={50}
                step={1}
                w="150px"
              >
                <SliderTrack>
                  <SliderFilledTrack />
                </SliderTrack>
                <SliderThumb />
              </Slider>
            </HStack>
          </HStack>

          {showIncompleteWarning && (
            <Box p={3} bg="yellow.50" borderRadius="md" borderWidth="1px" borderColor="yellow.200">
              <Text fontSize="sm" color="yellow.800">
                Showing distribution for loaded results only. Full histogram requires task selection.
              </Text>
            </Box>
          )}

          {error && (
            <Box p={3} bg="red.50" borderRadius="md" borderWidth="1px" borderColor="red.200">
              <Text fontSize="sm" color="red.800">
                Failed to load histogram: {error}
              </Text>
            </Box>
          )}

          {loading && displayData.length === 0 ? (
            <Box textAlign="center" py={8}>
              <Spinner />
            </Box>
          ) : displayData.length > 0 ? (
            <Box
              w="100%"
              overflowX="auto"
              py={4}
               css={{
                 '&::-webkit-scrollbar': {
                   height: '8px',
                 },
                 '&::-webkit-scrollbar-track': {
                   bg: scrollbarTrackBg,
                   borderRadius: '4px',
                 },
                 '&::-webkit-scrollbar-thumb': {
                   bg: scrollbarThumbBg,
                   borderRadius: '4px',
                 },
               }}
            >
              <HStack
                align="flex-end"
                spacing={0}
                h="200px"
                w="100%"
                maxW="1200px"
                mx="auto"
                px={2}
                borderBottom="1px solid"
                borderColor={chartBorderColor}
              >
                 {displayData.map((bin, index) => {
                   const rawCount = bin.count || 0;
                   const scaledValue = isLogScale 
                     ? Math.log10(rawCount + 1)
                     : rawCount;
                   const maxVal = isLogScale ? maxLog : maxLinear;
                   const barHeight = (scaledValue / maxVal) * 160;
                   const percentage = totalPairs > 0 ? ((rawCount / totalPairs) * 100).toFixed(1) : '0.0';
                   const barColor = getBarColor(bin.range);
                   const barWidthPercent = 100 / displayData.length;
                   const showLabel = index % labelStep === 0;

                   return (
                     <Tooltip
                       key={index}
                       label={`${bin.range}: ${rawCount.toLocaleString()} pairs (${percentage}%)${isLogScale ? ' [log]' : ''}`}
                       placement="top"
                     >
                       <VStack
                         spacing={1}
                         align="center"
                         flex="none"
                         w={`${barWidthPercent}%`}
                         maxW={`${Math.max(40, 600 / displayData.length)}px`}
                         minW="20px"
                         cursor="pointer"
                       >
                         <Text fontSize="xs" fontWeight="bold" color={textColor} mb={1}>
                           {rawCount > 0 ? rawCount.toLocaleString() : '-'}
                         </Text>
                         <Box
                           bg={barColor}
                           _hover={{ opacity: 0.8 }}
                           borderRadius="sm"
                           style={{
                             height: `${barHeight}px`,
                             width: '100%',
                             transition: 'height 0.2s ease',
                           }}
                         />
                         <Text fontSize="10px" color={rangeColor} mt={1} whiteSpace="nowrap" opacity={showLabel ? 1 : 0}>
                           {bin.range}
                         </Text>
                       </VStack>
                     </Tooltip>
                   );
                 })}
              </HStack>
            </Box>
          ) : null}

          {/* Summary */}
          <HStack justify="center" spacing={6} pt={2}>
            <VStack align="center" spacing={1}>
              <Text fontSize="sm" fontWeight="bold" color="green.500">
                {stats?.low?.toLocaleString() ?? '0'}
              </Text>
              <Text fontSize="xs" color={rangeColor}>Low (&lt;25%)</Text>
            </VStack>
            <VStack align="center" spacing={1}>
              <Text fontSize="sm" fontWeight="bold" color="orange.500">
                {stats?.medium?.toLocaleString() ?? '0'}
              </Text>
              <Text fontSize="xs" color={rangeColor}>Medium (25-49%)</Text>
            </VStack>
            <VStack align="center" spacing={1}>
              <Text fontSize="sm" fontWeight="bold" color="red.500">
                {stats?.high?.toLocaleString() ?? '0'}
              </Text>
              <Text fontSize="xs" color={rangeColor}>High (≥50%)</Text>
            </VStack>
            <VStack align="center" spacing={1}>
              <Text fontSize="sm" fontWeight="bold" color="blue.500">
                {totalPairs.toLocaleString()}
              </Text>
              <Text fontSize="xs" color={rangeColor}>Total</Text>
            </VStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default SimilarityDistribution;
