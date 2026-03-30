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
  Tooltip,
} from '@chakra-ui/react';
import type { PlagiarismMatch } from '../../types';
import {
  PLAGIARISM_TYPE_COLORS,
  PLAGIARISM_TYPE_COLORS_HOVER,
  PLAGIARISM_TYPE_BORDERS,
  PLAGIARISM_TYPE_LABELS,
} from '../../types';

// Fallback colors for matches without type info (backward compat)
const FALLBACK_COLORS = [
  'rgba(255, 235, 59, 0.3)',
  'rgba(76, 175, 80, 0.25)',
  'rgba(33, 150, 243, 0.25)',
  'rgba(156, 39, 176, 0.25)',
];

const FALLBACK_BORDERS = ['#FBC02D', '#388E3C', '#1976D2', '#7B1FA2'];

const isCommentLine = (line: string, language: string): boolean => {
  const trimmed = line.trim();
  if (!trimmed) return false;

  // Python / Ruby / Bash — line comments only
  if (['python', 'ruby', 'perl', 'bash', 'shell'].includes(language)) {
    return trimmed.startsWith('#');
  }

  // C-style languages — line comments and block comment delimiters
  if (['javascript', 'typescript', 'tsx', 'c', 'cpp', 'java', 'go', 'rust', 'kotlin', 'swift', 'csharp'].includes(language)) {
    return trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed === '*' || trimmed.startsWith('*/');
  }

  // SQL / Lua
  if (['sql', 'lua'].includes(language)) {
    return trimmed.startsWith('--');
  }

  // HTML / XML
  if (language === 'html' || language === 'xml') {
    return trimmed.startsWith('<!--') || trimmed.endsWith('-->');
  }

  // CSS / SCSS
  if (['css', 'scss', 'less'].includes(language)) {
    return trimmed.startsWith('/*') || trimmed === '*' || trimmed.startsWith('*/');
  }

  return false;
};

const getMatchBg = (match: PlagiarismMatch | null, isHovered: boolean): string => {
  if (!match) return 'transparent';
  const ptype = match.plagiarism_type;
  if (ptype && PLAGIARISM_TYPE_COLORS[ptype]) {
    return isHovered
      ? PLAGIARISM_TYPE_COLORS_HOVER[ptype]
      : PLAGIARISM_TYPE_COLORS[ptype];
  }
  // Fallback: use index-based coloring
  return isHovered ? 'rgba(255, 235, 59, 0.7)' : FALLBACK_COLORS[0];
};

const getMatchBorder = (match: PlagiarismMatch | null): string => {
  if (!match) return 'transparent';
  const ptype = match.plagiarism_type;
  if (ptype && PLAGIARISM_TYPE_BORDERS[ptype]) {
    return PLAGIARISM_TYPE_BORDERS[ptype];
  }
  return FALLBACK_BORDERS[0];
};

const getMatchTooltip = (match: PlagiarismMatch | null): string => {
  if (!match) return '';
  const ptype = match.plagiarism_type;
  const label = ptype ? (PLAGIARISM_TYPE_LABELS[ptype] || `Type ${ptype}`) : 'Match';
  if (match.description) {
    return `${label}: ${match.description}`;
  }
  if (match.details?.renames && match.details.renames.length > 0) {
    const renames = (match.details.renames as Array<{ original: string; renamed: string }>)
      .map((r) => `${r.original} → ${r.renamed}`).join(', ');
    return `${label}: ${renames}`;
  }
  return label;
};

interface FileViewerProps {
  content: string;
  fileName: string;
  language: string;
  matches: PlagiarismMatch[];
  isFileA: boolean;
  filterComments: boolean;
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
  filterComments,
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
    const map: Array<{ matchIndex: number; match: PlagiarismMatch } | null> = new Array(lines.length).fill(null);
    matches.forEach((match, index) => {
      const startLine = isFileA ? match.file_a_start_line : match.file_b_start_line;
      const endLine = isFileA ? match.file_a_end_line : match.file_b_end_line;
      for (let lineNum = Math.max(1, startLine); lineNum <= endLine && lineNum <= lines.length; lineNum++) {
        const idx = lineNum - 1;
        if (map[idx] === null) {
          map[idx] = { matchIndex: index, match };
        }
      }
    });
    return map;
  }, [lines.length, matches, isFileA]);

  const displayedLines = useMemo(() => {
    const result: Array<{ originalIdx: number; originalLineNumber: number; line: string }> = [];
    lines.forEach((line, idx) => {
      if (filterComments && isCommentLine(line, language)) return;
      result.push({ originalIdx: idx, originalLineNumber: idx + 1, line });
    });
    return result;
  }, [lines, filterComments, language]);

  const handleClick = useCallback((lineNumber: number, event: React.SyntheticEvent) => {
    const lineEl = event.currentTarget as HTMLDivElement;
    const container = scrollContainerRef.current;
    if (!container) return;
    const lineRect = lineEl.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const targetViewportOffset = lineRect.top - containerRect.top - (parseFloat(getComputedStyle(container).borderTopWidth) || 0);
    onJumpToMatch(lineNumber, targetViewportOffset, isFileA);
  }, [scrollContainerRef, onJumpToMatch, isFileA]);

  return (
    <Card flex={1} display="flex" flexDirection="column" overflow="hidden">
      <CardBody p={0} flex={1} display="flex" flexDirection="column" overflow="hidden">
        <Flex direction="column" h="100%" minH={0}>
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
            {displayedLines.map(({ originalIdx, originalLineNumber, line }, displayIdx) => {
              const matchInfo = lineMatchMap[originalIdx];
              const isHovered = matchInfo !== null && matchInfo.matchIndex === hoveredMatchIndex;
              const tooltip = getMatchTooltip(matchInfo?.match ?? null);
              const bg = getMatchBg(matchInfo?.match ?? null, isHovered);
              const border = getMatchBorder(matchInfo?.match ?? null);

              return (
                <Flex
                  key={originalIdx}
                  ref={(el) => getLineRef(originalIdx, el)}
                  bg={bg}
                  borderLeftWidth={matchInfo ? 4 : 0}
                  borderLeftColor={border}
                  onMouseEnter={() => onHoverMatch(matchInfo ? matchInfo.matchIndex : null)}
                  onMouseLeave={() => onHoverMatch(null)}
                  onClick={(e) => matchInfo && handleClick(originalLineNumber, e)}
                  cursor={matchInfo ? 'pointer' : 'default'}
                  role={matchInfo ? 'button' : undefined}
                  tabIndex={matchInfo ? 0 : undefined}
                  minW="fit-content"
                  title={tooltip || undefined}
                  onKeyDown={(e) => {
                    if (matchInfo && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      handleClick(originalLineNumber, e);
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
                    {originalLineNumber}
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
                  {matchInfo?.match?.plagiarism_type && matchInfo.match.plagiarism_type >= 2 && (
                    <Tooltip label={PLAGIARISM_TYPE_LABELS[matchInfo.match.plagiarism_type] || `Type ${matchInfo.match.plagiarism_type}`} placement="top">
                      <Badge
                        size="sm"
                        colorScheme={
                          matchInfo.match.plagiarism_type === 2 ? 'yellow' :
                          matchInfo.match.plagiarism_type === 3 ? 'blue' :
                          matchInfo.match.plagiarism_type === 4 ? 'red' : 'gray'
                        }
                        mr={2}
                        alignSelf="center"
                        fontSize="2xs"
                        opacity={0.8}
                      >
                        T{matchInfo.match.plagiarism_type}
                      </Badge>
                    </Tooltip>
                  )}
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
