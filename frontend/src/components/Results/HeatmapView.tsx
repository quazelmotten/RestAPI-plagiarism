import React, { useMemo } from 'react';
import { Box, Text, Tooltip, Card, CardBody, Heading } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import type { TaskDetails, PlagiarismResult } from '../../types';

interface HeatmapViewProps {
  selectedTask: TaskDetails;
  handleCompare: (result: PlagiarismResult) => void;
  cardBg?: string;
}

const MAX_HEATMAP_FILES = 30;

const HeatmapView: React.FC<HeatmapViewProps> = ({ selectedTask, handleCompare, cardBg }) => {
  const { t } = useTranslation(['results']);

  // Pre-index results into a Map for O(1) lookup instead of O(M) find()
  const resultIndex = useMemo(() => {
    const map = new Map<string, PlagiarismResult>();
    for (const r of selectedTask.results) {
      const key1 = `${r.file_a.id}|${r.file_b.id}`;
      const key2 = `${r.file_b.id}|${r.file_a.id}`;
      map.set(key1, r);
      map.set(key2, r);
    }
    return map;
  }, [selectedTask.results]);

  const allFiles = selectedTask.files;
  const tooManyFiles = allFiles.length > MAX_HEATMAP_FILES;
  const files = tooManyFiles ? allFiles.slice(0, MAX_HEATMAP_FILES) : allFiles;

  const matrix = useMemo(() => {
    const n = files.length;
    const mat: number[][] = new Array(n);
    for (let i = 0; i < n; i++) {
      mat[i] = new Array(n);
      for (let j = 0; j < n; j++) {
        if (i === j) {
          mat[i][j] = 1;
        } else {
          const result = resultIndex.get(`${files[i].id}|${files[j].id}`);
          mat[i][j] = result ? (result.ast_similarity || 0) : 0;
        }
      }
    }
    return mat;
  }, [files, resultIndex]);

  if (!selectedTask || allFiles.length < 2) return null;

  // Build index for cell click lookups
  const handleClick = (i: number, j: number) => {
    if (i === j) return;
    const result = resultIndex.get(`${files[i].id}|${files[j].id}`);
    if (result) handleCompare(result);
  };

  return (
    <Card bg={cardBg}>
      <CardBody>
        <Heading size="sm" mb={4}>
          {t('heatmap:title')}
          {tooManyFiles && (
            <Text as="span" fontWeight="normal" fontSize="xs" ml={2} color="gray.500">
              (showing {MAX_HEATMAP_FILES} of {allFiles.length} files)
            </Text>
          )}
        </Heading>

        {tooManyFiles ? (
          <Box overflowX="auto">
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ padding: '4px', fontSize: '11px', minWidth: '120px', textAlign: 'left', position: 'sticky', left: 0, background: 'inherit', zIndex: 1 }}></th>
                  {files.map((file, j) => (
                    <th key={j} style={{ padding: '4px', fontSize: '10px', textAlign: 'center', minWidth: '60px', maxWidth: '80px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {file.filename}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {files.map((fileA, i) => (
                  <tr key={i}>
                    <td style={{ padding: '4px', fontSize: '10px', fontWeight: 600, position: 'sticky', left: 0, background: 'inherit', zIndex: 1, minWidth: '120px', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {fileA.filename}
                    </td>
                    {files.map((fileB, j) => {
                      const sim = matrix[i][j];
                      const isDiag = i === j;
                      const cellStyle: React.CSSProperties = {
                        padding: '4px',
                        textAlign: 'center',
                        fontSize: '11px',
                        fontWeight: 'bold',
                        cursor: isDiag ? 'default' : 'pointer',
                        opacity: isDiag ? 0.5 : 1,
                        borderRadius: '2px',
                        minWidth: '60px',
                        color: 'white',
                      };

                      if (isDiag) {
                        cellStyle.background = '#e2e8f0';
                        cellStyle.color = '#a0aec0';
                      } else if (sim >= 0.8) {
                        cellStyle.background = '#ff6b6b';
                      } else if (sim >= 0.5) {
                        cellStyle.background = '#ffa726';
                      } else if (sim >= 0.3) {
                        cellStyle.background = '#ffca28';
                        cellStyle.color = '#333';
                      } else {
                        cellStyle.background = '#66bb6a';
                      }

                      return (
                        <td
                          key={j}
                          style={cellStyle}
                          onClick={() => handleClick(i, j)}
                          title={isDiag ? fileA.filename : `${fileA.filename} vs ${fileB.filename}: ${(sim * 100).toFixed(1)}%`}
                        >
                          {isDiag ? '—' : `${(sim * 100).toFixed(0)}%`}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>
        ) : (
          // Original Chakra UI heatmap for small file counts
          <Box overflowX="auto">
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ padding: '6px' }}></th>
                  {files.map((file, j) => (
                    <th key={j} style={{ padding: '6px', fontSize: '11px', textAlign: 'center', maxWidth: '80px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {file.filename}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {files.map((fileA, i) => (
                  <tr key={i}>
                    <td style={{ padding: '6px', fontSize: '11px', fontWeight: 600, maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {fileA.filename}
                    </td>
                    {files.map((fileB, j) => {
                      const sim = matrix[i][j];
                      const isDiag = i === j;
                      let bg = '#66bb6a';
                      if (isDiag) bg = '#e2e8f0';
                      else if (sim >= 0.8) bg = '#ff6b6b';
                      else if (sim >= 0.5) bg = '#ffa726';
                      else if (sim >= 0.3) bg = '#ffca28';

                      return (
                        <Tooltip
                          key={j}
                          label={isDiag ? fileA.filename : `${fileA.filename} vs ${fileB.filename}: ${(sim * 100).toFixed(1)}%`}
                          placement="top"
                        >
                          <td
                            style={{
                              padding: '6px',
                              textAlign: 'center',
                              fontSize: '12px',
                              fontWeight: 'bold',
                              cursor: isDiag ? 'default' : 'pointer',
                              opacity: isDiag ? 0.5 : 1,
                              background: bg,
                              color: isDiag ? '#a0aec0' : sim >= 0.3 && sim < 0.5 ? '#333' : 'white',
                              borderRadius: '4px',
                              minWidth: '70px',
                            }}
                            onClick={() => handleClick(i, j)}
                          >
                            {isDiag ? '—' : `${(sim * 100).toFixed(0)}%`}
                          </td>
                        </Tooltip>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>
        )}
      </CardBody>
    </Card>
  );
};

export default HeatmapView;
