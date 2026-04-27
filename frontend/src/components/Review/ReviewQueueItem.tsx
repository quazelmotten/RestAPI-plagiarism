import React, { useState } from 'react';
import {
  HStack, Text, Badge, Button, useToast, IconButton, Tooltip, useColorModeValue
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiCheck, FiX, FiEye } from 'react-icons/fi';
import api, { API_ENDPOINTS } from '../../services/api';
import type { PlagiarismResult } from '../../types';

interface ReviewQueueItemProps {
  item: PlagiarismResult;
  index: number;
  onReview: (pair: PlagiarismResult, allPairs?: PlagiarismResult[]) => void;
  onAction?: () => void;
}

const ReviewQueueItem: React.FC<ReviewQueueItemProps> = ({ 
  item, index, onReview, onAction 
}) => {
  const { t } = useTranslation(['review']);
  const [confirming, setConfirming] = useState(false);
  const [skipping, setSkipping] = useState(false);
  const toast = useToast();
  
  const isBothUnconfirmed = !item.file_a.is_confirmed && !item.file_b.is_confirmed;
  
  const itemBg = useColorModeValue(isBothUnconfirmed ? "blue.50" : "gray.50", isBothUnconfirmed ? "blue.900" : "gray.700");
  const itemBorderColor = useColorModeValue(isBothUnconfirmed ? "blue.200" : "gray.200", isBothUnconfirmed ? "blue.700" : "gray.600");
  const itemHoverBg = useColorModeValue(isBothUnconfirmed ? "blue.100" : "gray.100", isBothUnconfirmed ? "blue.800" : "gray.600");
  const mutedTextColor = useColorModeValue("gray.500", "gray.400");
  
  const handleConfirm = async () => {
    if (!item.id) return;
    setConfirming(true);
    try {
      await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(item.id));
      toast({
        title: t('review:confirmed'),
        description: t('review:pairMarkedAsPlagiarism'),
        status: 'success',
        duration: 2000,
      });
      onAction?.();
    } catch (error) {
      toast({
        title: t('common:errors.generic'),
        description: t('review:failedToAction', { action: 'confirm' }),
        status: 'error',
        duration: 3000,
      });
    } finally {
      setConfirming(false);
    }
  };
  
  const handleSkip = async () => {
    if (!item.id) return;
    setSkipping(true);
    try {
      await api.post(API_ENDPOINTS.CLEAR_PAIR(item.id));
      toast({
        title: 'Cleared',
        description: 'Pair marked as not plagiarism',
        status: 'info',
        duration: 2000,
      });
      onAction?.();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to clear',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setSkipping(false);
    }
};
   
  return (
    <HStack
      p={3}
      borderWidth={1}
      borderRadius="md"
      bg={itemBg}
      borderColor={itemBorderColor}
      _hover={{ bg: itemHoverBg }}
      transition="all 0.2s"
      role="listitem"
      aria-label={`${item.file_a.filename} vs ${item.file_b.filename}`}
    >
      <Badge colorScheme={isBothUnconfirmed ? "blue" : "gray"} mr={2}>
        {index + 1}
      </Badge>
      
      <HStack flex={1} spacing={2}>
        <Text fontSize="sm" fontWeight="medium">
          {item.file_a.filename}
        </Text>
        {item.file_a.is_confirmed && (
          <Badge colorScheme="green" size="sm">✓</Badge>
        )}
        <Text fontSize="sm" color={mutedTextColor}>vs</Text>
        <Text fontSize="sm" fontWeight="medium">
          {item.file_b.filename}
        </Text>
        {item.file_b.is_confirmed && (
          <Badge colorScheme="green" size="sm">✓</Badge>
        )}
      </HStack>
      
      <Badge colorScheme="orange" fontSize="md" px={2} py={1}>
        {((item.ast_similarity || 0) * 100).toFixed(1)}%
      </Badge>
      
      <HStack spacing={1}>
        <Tooltip label="Review in detail">
          <IconButton
            size="sm"
            icon={<FiEye />}
            aria-label={`Review ${item.file_a.filename} vs ${item.file_b.filename}`}
            onClick={() => onReview(item)}
            _focus={{ boxShadow: 'outline' }}
          />
        </Tooltip>
        
        <Tooltip label={t('review:confirmPlagiarism')}>
          <Button
            size="sm"
            colorScheme="green"
            leftIcon={<FiCheck />}
            onClick={handleConfirm}
            isLoading={confirming}
            _focus={{ boxShadow: 'outline' }}
          >
            {t('review:confirm')}
          </Button>
        </Tooltip>
        
        <Tooltip label={t('review:clearNoPlagiarism')}>
          <Button
            size="sm"
            colorScheme="gray"
            onClick={handleSkip}
            isLoading={skipping}
            _focus={{ boxShadow: 'outline' }}
          >
            {t('review:clear')}
          </Button>
        </Tooltip>
      </HStack>
    </HStack>
  );
};

export default ReviewQueueItem;
