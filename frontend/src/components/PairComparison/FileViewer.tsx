import React, { useMemo, useCallback } from 'react';
import {
  Card,
  CardBody,
  Flex,
  HStack,
  Text,
  Badge,
  useColorModeValue,
  Box,
} from '@chakra-ui/react';
import type { PlagiarismMatch } from '../../types';

const MATCH_COLORS = [
  'rgba(255, 235, 59, 0.3)',
  'rgba(76, 175, 80, 0.25)',
  'rgba(33, 150, 243, 0.25)',
  'rgba(156, 39, 176, 0.25)',
  'rgba(255, 87, 34, 0.25)',
  'rgba(0, 188, 212, 0.25)',
  'rgba(233, 30, 99, 0.25)',
  'rgba(255, 152, 0, 0.25)',
];

const MATCH_COLORS_HOVER = [
  'rgba(255, 235, 59, 0.7)',
  'rgba(76, 175, 80, 0.6)',
  'rgba(33, 150, 243, 0.6)',
  'rgba(156, 39, 176, 0.6)',
  'rgba(255, 87, 34, 0.6)',
  'rgba(0, 188, 212, 0.6)',
  'rgba(233, 30, 99, 0.6)',
  'rgba(255, 152, 0, 0.6)',
];

const MATCH_BORDERS = [
  '#FBC02D',
  '#388E3C',
  '#1976D2',
  '#7B1FA2',
  '#E64A19',
  '#0097A7',
  '#C2185B',
  '#F57C00',
];

const getMatchColor = (matchIndex: number) => MATCH_COLORS[matchIndex % MATCH_COLORS.length];
const getMatchColorHover = (matchIndex: number) => MATCH_COLORS_HOVER[matchIndex % MATCH_COLORS_HOVER.length];
const getMatchBorder = (matchIndex: number) => MATCH_BORDERS[matchIndex % MATCH_BORDERS.length];

interface FileViewerProps {
  content: string;
  fileName: string;
  language: string;
  matches: PlagiarismMatch[];
  isFileA: boolean;
  hoveredMatchIndex: number | null;
  onHoverMatch: (index: number | null) => void;
  onJumpToMatch: (clickedLine: number, clickedLineOffset: number, clickedIsFileA: boolean) => void;
  scrollContainerRef: React.RefObject<HTMLDivElement | null>;
  getLineRef: (lineIndex: number, el: HTMLDivElement | null) => void;
}

const FileViewer: React.FC<FileViewerProps> = ({
  content,
  fileName,
  language,
  matches,
  isFileA,
  hoveredMatchIndex,
  onHoverMatch,
  onJumpToMatch,
  scrollContainerRef,
  getLineRef,
}) => {
  const lineNumberBg = useColorModeValue('gray.100', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const lineNumberColor = useColorModeValue('gray.500', 'gray.400');

  const lines = useMemo(() => content.split('\n'), [content]);

  const lineMatchMap = useMemo(() => {
    const map: Array<{ matchIndex: number } | null> = new Array(lines.length).fill(null);
    matches.forEach((match, index) => {
      const startLine = isFileA ? match.file_a_start_line : match.file_b_start_line;
      const endLine = isFileA ? match.file_a_end_line : match.file_b_end_line;
      for (let lineNum = Math.max(1, startLine); lineNum <= endLine && lineNum <= lines.length; lineNum++) {
        const idx = lineNum - 1;
        if (map[idx] === null) {
          map[idx] = { matchIndex: index };
        }
      }
    });
    return map;
  }, [lines.length, matches, isFileA]);

  const handleClick = useCallback((lineNumber: number, event: React.SyntheticEvent) => {
    const lineEl = event.currentTarget as HTMLDivElement;
    const container = scrollContainerRef.current;
    if (!container) return;
    const offsetInContainer = lineEl.offsetTop - container.scrollTop;
    onJumpToMatch(lineNumber, offsetInContainer, isFileA);
  }, [scrollContainerRef, onJumpToMatch, isFileA]);

  return (
    <Card flex={1} display="flex" flexDirection="column">
      <CardBody p={0} flex={1} display="flex" flexDirection="column">
        <Flex direction="column" h="100%">
          <HStack p={3} borderBottomWidth={1} borderColor={borderColor} justify="space-between">
            <Text fontWeight="bold">{fileName}</Text>
            <Badge colorScheme={isFileA ? 'blue' : 'green'}>{language || 'unknown'}</Badge>
          </HStack>
          <Box
            ref={scrollContainerRef}
            flex={1}
            overflowY="auto"
            overflowX="auto"
            fontFamily="monospace"
            fontSize="sm"
            minW={0}
          >
            {lines.map((line, idx) => {
              const lineNumber = idx + 1;
              const matchInfo = lineMatchMap[idx];
              const isHovered = matchInfo !== null && matchInfo.matchIndex === hoveredMatchIndex;
              return (
                <Flex
                  key={idx}
                  ref={(el) => getLineRef(idx, el)}
                  bg={isHovered
                    ? getMatchColorHover(matchInfo!.matchIndex)
                    : (matchInfo ? getMatchColor(matchInfo.matchIndex) : 'transparent')}
                  borderLeftWidth={matchInfo ? 4 : 0}
                  borderLeftColor={matchInfo ? getMatchBorder(matchInfo.matchIndex) : 'transparent'}
                  onMouseEnter={() => onHoverMatch(matchInfo ? matchInfo.matchIndex : null)}
                  onMouseLeave={() => onHoverMatch(null)}
                  onClick={(e) => matchInfo && handleClick(lineNumber, e)}
                  cursor={matchInfo ? 'pointer' : 'default'}
                  role={matchInfo ? 'button' : undefined}
                  tabIndex={matchInfo ? 0 : undefined}
                  minW="fit-content"
                  onKeyDown={(e) => {
                    if (matchInfo && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      handleClick(lineNumber, e);
                    }
                  }}
                >
                  <Box
                    w="50px"
                    minW="50px"
                    bg={lineNumberBg}
                    textAlign="right"
                    pr={2}
                    py={0.5}
                    color={lineNumberColor}
                    fontSize="xs"
                    borderRightWidth={1}
                    borderRightColor={borderColor}
                    userSelect="none"
                  >
                    {lineNumber}
                  </Box>
                  <Box
                    flex={1}
                    pl={3}
                    py={0.5}
                    whiteSpace="pre-wrap"
                    wordBreak="break-word"
                    color={textColor}
                    minWidth={0}
                  >
                    {line || ' '}
                  </Box>
                </Flex>
              );
            })}
          </Box>
        </Flex>
      </CardBody>
    </Card>
  );
};

export default FileViewer;
