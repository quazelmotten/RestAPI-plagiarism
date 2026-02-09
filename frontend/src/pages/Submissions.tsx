import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
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
  Spinner,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';
import { FiEye } from 'react-icons/fi';
import api from '../services/api';

interface FileSubmission {
  id: string;
  filename: string;
  language: string;
  created_at: string;
  task_id: string;
  status: string;
  similarity: number | null;
}

const Submissions: React.FC = () => {
  const [submissions, setSubmissions] = useState<FileSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchSubmissions();
  }, []);

  const fetchSubmissions = async () => {
    try {
      setLoading(true);
      console.log('Fetching submissions from /plagiarism/files/all');
      const response = await api.get('/plagiarism/files/all');
      console.log('Response:', response.data);
      setSubmissions(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching submissions:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to fetch submissions';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleViewComparison = (submissionId: string) => {
    // Navigate to results page and filter for this submission
    navigate(`/dashboard/results?filter=${submissionId}`);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'green';
      case 'processing':
        return 'yellow';
      case 'queued':
        return 'gray';
      case 'failed':
        return 'red';
      default:
        return 'gray';
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" h="400px">
        <Spinner size="xl" color="blue.500" />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert status="error">
        <AlertIcon />
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Heading mb={6}>Submissions</Heading>

      <Card>
        <CardBody>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>File Name</Th>
                <Th>Language</Th>
                <Th>Status</Th>
                <Th>Similarity</Th>
                <Th>Submitted At</Th>
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
                submissions.map((submission) => (
                  <Tr key={submission.id}>
                    <Td>{submission.filename}</Td>
                    <Td>
                      <Badge colorScheme="blue" variant="outline">
                        {submission.language}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(submission.status)}>
                        {submission.status}
                      </Badge>
                    </Td>
                    <Td>
                      {submission.similarity !== null && submission.similarity !== undefined
                        ? `${(submission.similarity * 100).toFixed(1)}%`
                        : '-'}
                    </Td>
                    <Td>{formatDate(submission.created_at)}</Td>
                    <Td>
                      <Button 
                        size="sm" 
                        leftIcon={<FiEye />} 
                        variant="ghost"
                        onClick={() => handleViewComparison(submission.id)}
                      >
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
