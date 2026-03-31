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
  useColorModeValue,
} from '@chakra-ui/react';
import { FiFolder } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation(['pairComparison', 'common']);
  const instructionColor = useColorModeValue('gray.600', 'gray.400');

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
              title={t('header.title')}
            >
              {selectedFileA && selectedFileB
                ? `${selectedFileA.filename} ${t('common.vs')} ${selectedFileB.filename}`
                : t('header.noSelection')}
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

          <Text fontSize="sm" color={instructionColor} textAlign="center">
            {t('header.instruction')}
          </Text>

          {analyzingMatches && (
            <HStack justify="center">
              <Spinner size="sm" />
              <Text fontSize="sm" color="blue.500">{t('header.computing')}</Text>
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
