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
  HStack,
  Select,
  Text,
  useColorModeValue,
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
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(0); // offset
  const [pageSize, setPageSize] = useState(50);
  const navigate = useNavigate();

  const borderColor = useColorModeValue('gray.200', 'gray.700');

  useEffect(() => {
    fetchSubmissions();
  }, []);

  const fetchSubmissions = async (offset: number = currentPage, limit: number = pageSize) => {
    try {
      setLoading(true);
      const response = await api.get('/plagiarism/files', {
        params: { limit, offset }
      });
      
      // Response is {files: FileSubmission[], total: number}
      if (!response.data || !Array.isArray(response.data.files)) {
        setError('Invalid data format received from server');
        setSubmissions([]);
        setTotalCount(0);
        return;
      }
      
      setSubmissions(response.data.files);
      setTotalCount(response.data.total || 0);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching submissions:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to fetch submissions';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (newOffset: number) => {
    setCurrentPage(newOffset);
    fetchSubmissions(newOffset, pageSize);
  };

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newSize = parseInt(e.target.value, 10);
    setPageSize(newSize);
    setCurrentPage(0); // reset to first page
    fetchSubmissions(0, newSize);
  };

  const handleViewComparison = (submissionId: string) => {
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
          
          {/* Pagination Controls */}
          {totalCount > pageSize && (
            <Box mt={4} pt={4} borderTopWidth={1} borderColor={borderColor}>
              <HStack justify="space-between" align="center" wrap="wrap" spacing={4}>
                <HStack spacing={2}>
                  <Button
                    size="sm"
                    onClick={() => handlePageChange(Math.max(0, currentPage - pageSize))}
                    isDisabled={currentPage === 0}
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handlePageChange(currentPage + pageSize)}
                    isDisabled={currentPage + pageSize >= totalCount}
                  >
                    Next
                  </Button>
                </HStack>
                
                <HStack spacing={2}>
                  <Text fontSize="sm" color="gray.600">
                    Page Size:
                  </Text>
                  <Select
                    value={pageSize.toString()}
                    onChange={handlePageSizeChange}
                    w="80px"
                    size="sm"
                  >
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                  </Select>
                </HStack>
                
                <Text fontSize="sm" color="gray.500">
                  Showing {Math.min(currentPage + 1, totalCount)} - {Math.min(currentPage + pageSize, totalCount)} of {totalCount} files
                </Text>
              </HStack>
            </Box>
          )}
        </CardBody>
      </Card>
    </Box>
  );
};

export default Submissions;
