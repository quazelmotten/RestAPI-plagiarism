import React from 'react';
import { Box, Grid, GridItem, Text, Tooltip, Card, CardBody, Heading } from '@chakra-ui/react';
import type { TaskDetails, PlagiarismResult } from '../../types';

interface HeatmapViewProps {
  selectedTask: TaskDetails;
  getSimilarityGradient: (similarity: number) => string;
  handleCompare: (result: PlagiarismResult) => void;
  cardBg?: string;
}

const HeatmapView: React.FC<HeatmapViewProps> = ({ selectedTask, getSimilarityGradient, handleCompare, cardBg }) => {
  if (!selectedTask || selectedTask.files.length < 2) return null;

  const files = selectedTask.files;
  const matrix: number[][] = [];

  for (let i = 0; i < files.length; i++) {
    matrix[i] = [];
    for (let j = 0; j < files.length; j++) {
      if (i === j) {
        matrix[i][j] = 1;
      } else {
        const result = selectedTask.results.find(
          (r: PlagiarismResult) =>
            (r.file_a.id === files[i].id && r.file_b.id === files[j].id) ||
            (r.file_a.id === files[j].id && r.file_b.id === files[i].id)
        );
        matrix[i][j] = result ? (result.ast_similarity || 0) : 0;
      }
    }
  }

  return (
    <Card bg={cardBg}>
      <CardBody>
        <Heading size="sm" mb={4}>Similarity Heatmap</Heading>
        <Box overflowX="auto">
          <Grid
            templateColumns={`repeat(${files.length + 1}, minmax(80px, 1fr))`}
            gap={2}
            p={4}
          >
            {/* Header row */}
            <GridItem />
            {files.map((file: { id: string; filename: string }, idx: number) => (
              <GridItem key={idx}>
                <Text
                  fontSize="xs"
                  fontWeight="semibold"
                  textAlign="center"
                  noOfLines={2}
                  h="40px"
                >
                  {file.filename}
                </Text>
              </GridItem>
            ))}

            {/* Data rows */}
            {files.map((fileA: { id: string; filename: string }, i: number) => (
              <React.Fragment key={i}>
                <GridItem display="flex" alignItems="center">
                  <Text
                    fontSize="xs"
                    fontWeight="semibold"
                    noOfLines={2}
                  >
                    {fileA.filename}
                  </Text>
                </GridItem>
                {files.map((fileB: { id: string; filename: string }, j: number) => (
                  <GridItem key={j}>
                    <Tooltip
                      label={i === j ? fileA.filename : `${fileA.filename} vs ${fileB.filename}: ${(matrix[i][j] * 100).toFixed(1)}%`}
                      placement="top"
                    >
                      <Box
                        w="100%"
                        h="100%"
                        minH="60px"
                        bg={i === j ? 'gray.200' : getSimilarityGradient(matrix[i][j])}
                        color={i === j ? 'gray.500' : 'white'}
                        display="flex"
                        alignItems="center"
                        justifyContent="center"
                        fontSize="sm"
                        fontWeight="bold"
                        borderRadius="md"
                        cursor={i === j ? 'default' : 'pointer'}
                        opacity={i === j ? 0.5 : 1}
                        onClick={() => {
                          if (i !== j) {
                            const result = selectedTask?.results.find(
                              (r) => (r.file_a.id === files[i].id && r.file_b.id === files[j].id) ||
                                   (r.file_a.id === files[j].id && r.file_b.id === files[i].id)
                            );
                            if (result) handleCompare(result);
                          }
                        }}
                      >
                        {i === j ? '—' : `${(matrix[i][j] * 100).toFixed(0)}%`}
                      </Box>
                    </Tooltip>
                  </GridItem>
                ))}
              </React.Fragment>
            ))}
          </Grid>
        </Box>
      </CardBody>
    </Card>
  );
};

export default HeatmapView;
