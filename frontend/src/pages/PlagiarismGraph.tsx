import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import {
  Box,
  Heading,
  Text,
  Card,
  CardBody,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  VStack,
  HStack,
  Badge,
} from '@chakra-ui/react';

cytoscape.use(coseBilkent);

const PlagiarismGraph: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.75);
  const [, setCy] = useState<cytoscape.Core | null>(null);

  // Placeholder data - will be replaced with API call
  const networkData = {
    nodes: [
      { id: '1', label: 'Student A', group: '1' },
      { id: '2', label: 'Student B', group: '2' },
      { id: '3', label: 'Student C', group: '2' },
      { id: '4', label: 'Student D', group: '1' },
      { id: '5', label: 'Student E', group: '3' },
    ],
    edges: [
      { source: '1', target: '2', similarity: 0.85 },
      { source: '2', target: '3', similarity: 0.92 },
      { source: '1', target: '4', similarity: 0.45 },
      { source: '3', target: '4', similarity: 0.78 },
      { source: '4', target: '5', similarity: 0.65 },
    ],
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: cytoscape.ElementDefinition[] = [
      ...networkData.nodes.map((node) => ({
        data: {
          id: node.id,
          label: node.label,
          group: node.group,
        },
      })),
      ...networkData.edges
        .filter((edge) => edge.similarity >= similarityThreshold)
        .map((edge) => ({
          data: {
            source: edge.source,
            target: edge.target,
            similarity: edge.similarity,
          },
        })),
    ];

    const newCy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#4299e1',
            'label': 'data(label)',
            'width': 50,
            'height': 50,
            'font-size': '14px',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#fff',
            'text-outline-color': '#2b6cb0',
            'text-outline-width': 2,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 3,
            'line-color': '#718096',
            'target-arrow-color': '#718096',
            'curve-style': 'bezier',
            'label': (ele: cytoscape.EdgeSingular) => 
              `${(ele.data('similarity') * 100).toFixed(0)}%`,
            'font-size': '12px',
            'text-background-color': '#fff',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
          },
        },
        {
          selector: 'edge[similarity >= 0.8]',
          style: {
            'line-color': '#e53e3e',
            'target-arrow-color': '#e53e3e',
            'width': 4,
          },
        },
        {
          selector: 'edge[similarity >= 0.6][similarity < 0.8]',
          style: {
            'line-color': '#ecc94b',
            'target-arrow-color': '#ecc94b',
            'width': 3,
          },
        },
        {
          selector: 'edge[similarity < 0.6]',
          style: {
            'line-color': '#48bb78',
            'target-arrow-color': '#48bb78',
            'width': 2,
          },
        },
      ],
      layout: {
        name: 'cose-bilkent',
        padding: 10,
        nodeRepulsion: 4500,
        idealEdgeLength: 100,
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        tile: true,
        tilingPaddingVertical: 10,
        tilingPaddingHorizontal: 10,
        gravityRangeCompound: 1.5,
        gravityCompound: 1.0,
        gravityRange: 3.8,
      } as any,
    });

    setCy(newCy);

    return () => {
      newCy.destroy();
    };
  }, [similarityThreshold]);

  return (
    <Box>
      <Heading mb={6}>Plagiarism Network</Heading>

      <Card mb={6}>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <HStack justify="space-between">
              <Text fontWeight="semibold">Similarity Threshold</Text>
              <Badge colorScheme="blue">{(similarityThreshold * 100).toFixed(0)}%</Badge>
            </HStack>
            <Slider
              value={similarityThreshold}
              onChange={setSimilarityThreshold}
              min={0}
              max={1}
              step={0.05}
            >
              <SliderTrack>
                <SliderFilledTrack />
              </SliderTrack>
              <SliderThumb />
            </Slider>
            <Text fontSize="sm" color="gray.500">
              Only show connections with similarity score above the threshold
            </Text>
            <HStack spacing={4} fontSize="sm">
              <HStack>
                <Box w="3" h="3" bg="red.500" borderRadius="full" />
                <Text>High (≥80%)</Text>
              </HStack>
              <HStack>
                <Box w="3" h="3" bg="yellow.400" borderRadius="full" />
                <Text>Medium (60-79%)</Text>
              </HStack>
              <HStack>
                <Box w="3" h="3" bg="green.400" borderRadius="full" />
                <Text>Low (&lt;60%)</Text>
              </HStack>
            </HStack>
          </VStack>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <Box
            ref={containerRef}
            height="600px"
            border="1px"
            borderColor="gray.200"
            borderRadius="md"
          />
        </CardBody>
      </Card>
    </Box>
  );
};

export default PlagiarismGraph;
