import React from 'react';
import { Box } from '@chakra-ui/react';
import ReviewQueue from '../../../components/Review/ReviewQueue';
import type { PlagiarismResult } from '../../../types';

interface AssignmentReviewTabProps {
  assignmentId: string;
  onReviewPair: (pair: PlagiarismResult, allPairs?: PlagiarismResult[]) => void;
}

const AssignmentReviewTab: React.FC<AssignmentReviewTabProps> = ({
  assignmentId,
  onReviewPair,
}) => {
  return (
    <Box flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden">
      <ReviewQueue
        assignmentId={assignmentId}
        onReviewPair={onReviewPair}
      />
    </Box>
  );
};

export default AssignmentReviewTab;
