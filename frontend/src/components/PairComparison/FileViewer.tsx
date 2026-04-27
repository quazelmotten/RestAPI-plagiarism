import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import {
  Card,
  CardBody,
  Flex,
  HStack,
  Text,
  Badge,
  useColorModeValue,
  useColorMode,
  Box,
  Tooltip,
} from '@chakra-ui/react';
import { Highlight, themes } from 'prism-react-renderer';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useTranslation } from 'react-i18next';
import type { PlagiarismMatch } from '../../types';
import {
  PLAGIARISM_TYPE_COLORS,
  PLAGIARISM_TYPE_COLORS_HOVER,
  PLAGIARISM_TYPE_BORDERS,
} from '../../types';

const prismLanguageMap: Record<string, string> = {
  javascript: 'javascript',
  typescript: 'typescript',
  tsx: 'tsx',
  jsx: 'jsx',
  python: 'python',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  csharp: 'csharp',
  'csharp.net': 'csharp',
  go: 'go',
  rust: 'rust',
  ruby: 'ruby',
  php: 'php',
  swift: 'swift',
  kotlin: 'kotlin',
  sql: 'sql',
  lua: 'lua',
  html: 'markup',
  xml: 'markup',
  css: 'css',
  scss: 'scss',
  less: 'less',
  bash: 'bash',
  shell: 'bash',
  sh: 'bash',
  json: 'json',
  yaml: 'yaml',
  markdown: 'markdown',
  md: 'markdown',
};

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
    return trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*') || trimmed.startsWith('*/');
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
    return trimmed.startsWith('/*') || trimmed.startsWith('*') || trimmed.startsWith('*/');
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

const getMatchTooltip = (match: PlagiarismMatch | null, t: (key: string, opts?: any) => string): string => {
  if (!match) return '';
  const ptype = match.plagiarism_type;
  const label = ptype ? t(`page.matchTypes.${ptype}`) : t('page.match');
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
  filterEmpty: boolean;
  syntaxHighlight: boolean;
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
  filterEmpty,
  syntaxHighlight,
  hoveredMatchIndex,
  onHoverMatch,
  onJumpToMatch,
  scrollContainerRef,
  getLineRef,
}) => {
  const { t } = useTranslation(['pairComparison', 'common']);
  const { colorMode } = useColorMode();
  const lineNumberBg = useColorModeValue('gray.100', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const lineNumberColor = useColorModeValue('gray.500', 'gray.400');
  const syntaxTheme = colorMode === 'dark' ? themes.vsDark : themes.vsLight;
  const containerRef = useRef<HTMLDivElement>(null);

  const LINE_HEIGHT = 24; // px per line (font-size sm + py)

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
    let lastLineWasEmpty = false;
    lines.forEach((line, idx) => {
      // Filter comments if enabled
      if (filterComments && isCommentLine(line, language)) return;
      const trimmed = line.trim();
      const isEmpty = trimmed === '';
      // Filter empty lines if enabled, collapsing consecutive empties into one
      if (filterEmpty && isEmpty) {
        if (lastLineWasEmpty) return;
        lastLineWasEmpty = true;
      } else {
        lastLineWasEmpty = false;
      }
      result.push({ originalIdx: idx, originalLineNumber: idx + 1, line });
    });
    return result;
  }, [lines, filterComments, filterEmpty, language, syntaxHighlight]);

  const handleClick = useCallback((lineNumber: number, event: React.SyntheticEvent) => {
    const lineEl = event.currentTarget as HTMLDivElement;
    const container = scrollContainerRef.current;
    if (!container) return;
    const lineRect = lineEl.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const targetViewportOffset = lineRect.top - containerRect.top - (parseFloat(getComputedStyle(container).borderTopWidth) || 0);
    onJumpToMatch(lineNumber, targetViewportOffset, isFileA);
  }, [scrollContainerRef, onJumpToMatch, isFileA]);

  const virtualizer = useVirtualizer({
    count: displayedLines.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => LINE_HEIGHT,
    overscan: 20,
  });

  // Sync the external scrollContainerRef with our internal ref
  useEffect(() => {
    if (containerRef.current && scrollContainerRef) {
      (scrollContainerRef as React.MutableRefObject<HTMLDivElement | null>).current = containerRef.current;
    }
  }, [scrollContainerRef]);

  return (
    <Card flex={1} display="flex" flexDirection="column" overflow="hidden">
      <CardBody p={0} flex={1} display="flex" flexDirection="column" overflow="hidden">
        <Flex direction="column" h="100%" minH={0}>
          <HStack p={3} borderBottomWidth={1} borderColor={borderColor} justify="space-between">
            <Text fontWeight="bold">{fileName}</Text>
             <Badge colorScheme={isFileA ? 'blue' : 'green'}>{language || t('common:unknown')}</Badge>
          </HStack>
          <Box
            ref={containerRef}
            flex={1}
            overflowY="auto"
            overflowX="auto"
            fontFamily="monospace"
            fontSize="sm"
            minW={0}
          >
            <div style={{ height: `${virtualizer.getTotalSize()}px`, width: '100%', position: 'relative' }}>
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const { originalIdx, originalLineNumber, line } = displayedLines[virtualRow.index];
                const matchInfo = lineMatchMap[originalIdx];
                const isHovered = matchInfo !== null && matchInfo.matchIndex === hoveredMatchIndex;
                const tooltip = getMatchTooltip(matchInfo?.match ?? null, t);
                const bg = getMatchBg(matchInfo?.match ?? null, isHovered);
                const border = getMatchBorder(matchInfo?.match ?? null);

                return (
                  <Flex
                    key={originalIdx}
                    ref={(el) => getLineRef(originalIdx, el)}
                    position="absolute"
                    top={0}
                    left={0}
                    width="100%"
                    transform={`translateY(${virtualRow.start}px)`}
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
                      {syntaxHighlight ? (
                        <Highlight
                          code={line}
                          language={prismLanguageMap[language] || 'text'}
                          theme={syntaxTheme}
                        >
                          {({ tokens, getLineProps, getTokenProps }) => (
                            <>
                              {tokens.map((lineTokens, lineIdx) => (
                                <span key={lineIdx} {...getLineProps({ line: lineTokens })}>
                                  {lineTokens.map((token, tokenIdx) => (
                                    <span key={tokenIdx} {...getTokenProps({ token })}>
                                      {token.content}
                                    </span>
                                  ))}
                                </span>
                              ))}
                            </>
                          )}
                        </Highlight>
                      ) : (
                        line || ' '
                      )}
                    </Box>
                    {matchInfo?.match?.plagiarism_type && matchInfo.match.plagiarism_type >= 2 && (
                        <Tooltip label={t(`page.matchTypes.${matchInfo.match.plagiarism_type}`)} placement="top">
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
            </div>
          </Box>
        </Flex>
      </CardBody>
    </Card>
  );
};

export default FileViewer;
