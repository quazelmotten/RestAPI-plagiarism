import React from 'react';
import {
  Box,
  Heading,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Card,
  CardBody,
  Button,
} from '@chakra-ui/react';
import { FiEye } from 'react-icons/fi';

const Submissions: React.FC = () => {
  // Placeholder data - will be replaced with API call
  const submissions: any[] = [];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'green';
      case 'processing':
        return 'yellow';
      case 'pending':
        return 'gray';
      case 'failed':
        return 'red';
      default:
        return 'gray';
    }
  };

  return (
    <Box>
      <Heading mb={6}>Submissions</Heading>

      <Card>
        <CardBody>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Student</Th>
                <Th>File Name</Th>
                <Th>Language</Th>
                <Th>Status</Th>
                <Th>Similarity</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {submissions.length === 0 ? (
                <Tr>
                  <Td colSpan={6} textAlign="center" py={8}>
                    No submissions found
                  </Td>
                </Tr>
              ) : (
                submissions.map((submission: any) => (
                  <Tr key={submission.id}>
                    <Td>{submission.studentName}</Td>
                    <Td>{submission.fileName}</Td>
                    <Td>{submission.language}</Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(submission.status)}>
                        {submission.status}
                      </Badge>
                    </Td>
                    <Td>
                      {submission.similarity
                        ? `${(submission.similarity * 100).toFixed(1)}%`
                        : '-'}
                    </Td>
                    <Td>
                      <Button size="sm" leftIcon={<FiEye />} variant="ghost">
                        View
                      </Button>
                    </Td>
                  </Tr>
                ))
              )}
            </Tbody>
          </Table>
        </CardBody>
      </Card>
    </Box>
  );
};

export default Submissions;
