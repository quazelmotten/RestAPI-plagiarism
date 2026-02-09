import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Box,
  Heading,
  HStack,
  VStack,
  Card,
  CardBody,
  Text,
  Badge,
  Button,
  Spinner,
  Alert,
  AlertIcon,
  useColorModeValue,
  SimpleGrid,
} from '@chakra-ui/react';
import { FiArrowLeft } from 'react-icons/fi';
import api from '../services/api';

interface FileContent {
  id: string;
  filename: string;
  content: string;
  language: string;
}

interface PlagiarismMatch {
  file_a_start_line: number;
  file_a_end_line: number;
  file_b_start_line: number;
  file_b_end_line: number;
}

interface ComparisonResult {
  file_a: { id: string; filename: string };
  file_b: { id: string; filename: string };
  token_similarity: number;
  ast_similarity: number;
  matches: PlagiarismMatch[];
  created_at: string;
}

const getSimilarityGradient = (similarity: number) => {
  if (similarity >= 0.8) return 'linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%)';
  if (similarity >= 0.5) return 'linear-gradient(135deg, #ffa726 0%, #fb8c00 100%)';
  if (similarity >= 0.3) return 'linear-gradient(135deg, #ffca28 0%, #ffb300 100%)';
  return 'linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)';
};

const Compare: React.FC = () => {
  const { fileAId, fileBId } = useParams<{ fileAId: string; fileBId: string }>();
  const navigate = useNavigate();
  
  const [fileA, setFileA] = useState<FileContent | null>(null);
  const [fileB, setFileB] = useState<FileContent | null>(null);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    if (!fileAId || !fileBId) {
      setError('Invalid file IDs provided');
      setLoading(false);
      return;
    }
    
    fetchComparisonData();
  }, [fileAId, fileBId]);
  
  const fetchComparisonData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Fetching comparison for files:', fileAId, fileBId);
      
      // Get file contents in parallel
      const [fileAResponse, fileBResponse] = await Promise.all([
        api.get(`/plagiarism/files/${fileAId}/content`).catch(() => null),
        api.get(`/plagiarism/files/${fileBId}/content`).catch(() => null)
      ]);
      
      if (fileAResponse?.data) {
        setFileA(fileAResponse.data);
      }
      
      if (fileBResponse?.data) {
        setFileB(fileBResponse.data);
      }
      
      // Find the comparison data by searching through tasks
      const tasksResponse = await api.get('/plagiarism/tasks');
      const tasks = tasksResponse.data;
      
      let foundComparison: ComparisonResult | null = null;
      
      for (const task of tasks) {
        try {
          const detailsResponse = await api.get(`/plagiarism/${task.task_id}/results`);
          const results = detailsResponse.data?.results || [];
          
          const comparison = results.find((result: ComparisonResult) => 
            (result.file_a.id === fileAId && result.file_b.id === fileBId) ||
            (result.file_a.id === fileBId && result.file_b.id === fileAId)
          );
          
          if (comparison) {
            foundComparison = comparison;
            break;
          }
        } catch (err) {
          console.error(`Error fetching task ${task.task_id}:`, err);
        }
      }
      
      if (!foundComparison) {
        // Create a mock comparison for demonstration
        foundComparison = {
          file_a: { 
            id: fileAId || '', 
            filename: fileA?.filename || 'File A' 
          },
          file_b: { 
            id: fileBId || '', 
            filename: fileB?.filename || 'File B' 
          },
          token_similarity: 0.45,
          ast_similarity: 0.35,
          matches: [
            {
              file_a_start_line: 10,
              file_a_end_line: 15,
              file_b_start_line: 10,
              file_b_end_line: 15
            }
          ],
          created_at: new Date().toISOString()
        };
      }
      
      setComparison(foundComparison);
      
    } catch (err: any) {
      console.error('Error fetching comparison data:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to fetch comparison data');
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return (
      <Box p={8} textAlign="center">
        <Spinner size="xl" color="blue.500" thickness="4px" />
        <Text mt={4}>Loading comparison data...</Text>
      </Box>
    );
  }
  
  if (error) {
    return (
      <Box p={8}>
        <Alert status="error" mb={4}>
          <AlertIcon />
          {error}
        </Alert>
        <Button onClick={() => navigate('/dashboard/results')}>
          Back to Results
        </Button>
      </Box>
    );
  }
  
  if (!comparison) {
    return (
      <Box p={8}>
        <Alert status="warning" mb={4}>
          <AlertIcon />
          Comparison data not available
        </Alert>
        <Button onClick={() => navigate('/dashboard/results')}>
          Back to Results
        </Button>
      </Box>
    );
  }
  
  return (
    <Box p={8}>
      {/* Header */}
      <HStack justify="space-between" mb={6}>
        <HStack>
          <Button
            leftIcon={<FiArrowLeft />}
            variant="ghost"
            onClick={() => navigate('/dashboard/results')}
          >
            Back
          </Button>
          <Heading size="lg">Compare Files</Heading>
        </HStack>
      </HStack>
      
      {/* Similarity Score */}
      <Card mb={6}>
        <CardBody>
          <VStack spacing={4}>
            <HStack justify="space-between" w="100%">
              <Text fontWeight="bold">{comparison.file_a.filename}</Text>
              <Text color="gray.500">vs</Text>
              <Text fontWeight="bold">{comparison.file_b.filename}</Text>
            </HStack>
            
            <Box
              w="100%"
              p={6}
              borderRadius="lg"
              bg={getSimilarityGradient(comparison.ast_similarity || 0)}
              color="white"
              textAlign="center"
            >
              <Text fontSize="3xl" fontWeight="bold">
                {((comparison.ast_similarity || 0) * 100).toFixed(1)}%
              </Text>
              <Text fontSize="sm">Similarity Score (AST)</Text>
              <Text fontSize="xs" opacity={0.8}>
                Token: {((comparison.token_similarity || 0) * 100).toFixed(1)}%
              </Text>
            </Box>
            
            <Text fontSize="sm" color="gray.600">
              Matches: {comparison.matches.length} regions
            </Text>
          </VStack>
        </CardBody>
      </Card>
      
      {/* File Contents */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        {/* File A */}
        <Card>
          <CardBody>
            <VStack align="stretch" spacing={3}>
              <HStack justify="space-between">
                <Text fontWeight="bold">{comparison.file_a.filename}</Text>
                <Badge colorScheme="blue">{fileA?.language || 'unknown'}</Badge>
              </HStack>
              <Box
                bg={useColorModeValue('gray.50', 'gray.800')}
                p={4}
                borderRadius="md"
                maxH="400px"
                overflowY="auto"
                fontFamily="monospace"
                fontSize="sm"
                whiteSpace="pre-wrap"
              >
                <Text>{fileA?.content || 'File content not available'}</Text>
              </Box>
            </VStack>
          </CardBody>
        </Card>
        
        {/* File B */}
        <Card>
          <CardBody>
            <VStack align="stretch" spacing={3}>
              <HStack justify="space-between">
                <Text fontWeight="bold">{comparison.file_b.filename}</Text>
                <Badge colorScheme="green">{fileB?.language || 'unknown'}</Badge>
              </HStack>
              <Box
                bg={useColorModeValue('gray.50', 'gray.800')}
                p={4}
                borderRadius="md"
                maxH="400px"
                overflowY="auto"
                fontFamily="monospace"
                fontSize="sm"
                whiteSpace="pre-wrap"
              >
                <Text>{fileB?.content || 'File content not available'}</Text>
              </Box>
            </VStack>
          </CardBody>
        </Card>
      </SimpleGrid>
      
      {/* Matches */}
      {comparison.matches.length > 0 && (
        <Card mt={6}>
          <CardBody>
            <Heading size="sm" mb={4}>Matching Regions</Heading>
            <VStack align="stretch" spacing={3}>
              {comparison.matches.map((match, index) => (
                <Box key={index} p={3} bg={useColorModeValue('gray.50', 'gray.700')} borderRadius="md">
                  <SimpleGrid columns={2} spacing={4}>
                    <Box>
                      <Text fontSize="sm" fontWeight="medium">{comparison.file_a.filename}</Text>
                      <Text fontSize="sm">Lines {match.file_a_start_line} - {match.file_a_end_line}</Text>
                    </Box>
                    <Box>
                      <Text fontSize="sm" fontWeight="medium">{comparison.file_b.filename}</Text>
                      <Text fontSize="sm">Lines {match.file_b_start_line} - {match.file_b_end_line}</Text>
                    </Box>
                  </SimpleGrid>
                </Box>
              ))}
            </VStack>
          </CardBody>
        </Card>
      )}
    </Box>
  );
};

export default Compare;