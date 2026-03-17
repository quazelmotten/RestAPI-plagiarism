import React from 'react';
import {
  Card,
  CardBody,
  VStack,
  HStack,
  Button,
  Text,
  Box,
  Spinner,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';
import { FiFolder } from 'react-icons/fi';
import type { FileInfo, PlagiarismResult } from '../../types';

interface ComparisonHeaderProps {
  selectedFileA: FileInfo | null;
  selectedFileB: FileInfo | null;
  currentPair: PlagiarismResult | null;
  getSimilarityGradient: (similarity: number) => string;
  onOpenPicker: () => void;
  analyzingMatches: boolean;
  contentError: string | null;
  bgColor?: string;
}

const ComparisonHeader: React.FC<ComparisonHeaderProps> = ({
  selectedFileA,
  selectedFileB,
  currentPair,
  getSimilarityGradient,
  onOpenPicker,
  analyzingMatches,
  contentError,
  bgColor,
}) => {
  return (
    <Card mb={4} bg={bgColor}>
      <CardBody>
        <VStack spacing={4}>
          <HStack spacing={4} w="100%" justify="center">
            <Button
              leftIcon={<FiFolder />}
              size="lg"
              variant="outline"
              flex={1}
              onClick={onOpenPicker}
              title="Select files to compare"
            >
              {selectedFileA && selectedFileB
                ? `${selectedFileA.filename} vs ${selectedFileB.filename}`
                : 'Select Files to Compare'}
            </Button>
            {currentPair && (
              <Box
                px={6}
                py={3}
                borderRadius="lg"
                bg={getSimilarityGradient(currentPair.ast_similarity || 0)}
                color="white"
                textAlign="center"
                minW="120px"
              >
                <Text fontSize="xl" fontWeight="bold">
                  {((currentPair.ast_similarity || 0) * 100).toFixed(1)}%
                </Text>
              </Box>
            )}
          </HStack>

          <Text fontSize="sm" color="gray.600" textAlign="center">
            Click any highlighted region to jump to the matching region in the other file
          </Text>

          {analyzingMatches && (
            <HStack justify="center">
              <Spinner size="sm" />
              <Text fontSize="sm" color="blue.500">Computing match details...</Text>
            </HStack>
          )}

          {contentError && (
            <Alert status="warning">
              <AlertIcon />
              {contentError}
            </Alert>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
};

export default ComparisonHeader;
