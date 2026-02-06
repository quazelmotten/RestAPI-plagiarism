import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Heading,
  Text,
  Button,
  VStack,
  HStack,
  Card,
  CardBody,
  Select,
  Progress,
  List,
  ListItem,
  Icon,
  Badge,
  useToast,
} from '@chakra-ui/react';
import { FiUploadCloud, FiFile, FiX } from 'react-icons/fi';
import api from '../services/api';

const Upload: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [language, setLanguage] = useState('python');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const toast = useToast();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prev) => [...prev, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt', '.py', '.js', '.ts', '.cpp', '.c', '.java'],
    },
    multiple: true,
  });

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      toast({
        title: 'No files selected',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      // Upload each file
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('language', language);

        await api.post('/submissions', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              ((i + (progressEvent.loaded / (progressEvent.total || 1))) / files.length) * 100
            );
            setUploadProgress(percentCompleted);
          },
        });
      }

      toast({
        title: 'Upload successful',
        description: `${files.length} file(s) uploaded successfully`,
        status: 'success',
        duration: 5000,
      });

      setFiles([]);
    } catch (error) {
      toast({
        title: 'Upload failed',
        description: 'There was an error uploading your files',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <Box>
      <Heading mb={6}>Upload Files</Heading>

      <VStack spacing={6} align="stretch">
        <Card>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <Text fontWeight="semibold">Select Programming Language</Text>
              <Select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                maxW="300px"
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="typescript">TypeScript</option>
                <option value="cpp">C++</option>
                <option value="c">C</option>
                <option value="java">Java</option>
                <option value="go">Go</option>
                <option value="rust">Rust</option>
              </Select>
            </VStack>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <Box
              {...getRootProps()}
              border="2px dashed"
              borderColor={isDragActive ? 'brand.500' : 'gray.300'}
              borderRadius="md"
              p={10}
              textAlign="center"
              cursor="pointer"
              bg={isDragActive ? 'brand.50' : 'transparent'}
              transition="all 0.2s"
            >
              <input {...getInputProps()} />
              <VStack spacing={2}>
                <Icon as={FiUploadCloud} boxSize={10} color="brand.500" />
                <Text fontSize="lg" fontWeight="medium">
                  {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
                </Text>
                <Text color="gray.500">or click to select files</Text>
                <Text fontSize="sm" color="gray.400">
                  Supported: .py, .js, .ts, .cpp, .c, .java, .go, .rs, .txt
                </Text>
              </VStack>
            </Box>
          </CardBody>
        </Card>

        {files.length > 0 && (
          <Card>
            <CardBody>
              <Text fontWeight="semibold" mb={4}>
                Selected Files ({files.length})
              </Text>
              <List spacing={2}>
                {files.map((file, index) => (
                  <ListItem key={index}>
                    <HStack justify="space-between" p={2} bg="gray.50" borderRadius="md">
                      <HStack>
                        <Icon as={FiFile} color="brand.500" />
                        <Text>{file.name}</Text>
                        <Badge size="sm">{(file.size / 1024).toFixed(1)} KB</Badge>
                      </HStack>
                      <Button
                        size="sm"
                        variant="ghost"
                        colorScheme="red"
                        onClick={() => removeFile(index)}
                        isDisabled={isUploading}
                      >
                        <Icon as={FiX} />
                      </Button>
                    </HStack>
                  </ListItem>
                ))}
              </List>

              {isUploading && (
                <Box mt={4}>
                  <Progress value={uploadProgress} size="sm" colorScheme="brand" />
                  <Text fontSize="sm" textAlign="center" mt={2}>
                    Uploading... {uploadProgress}%
                  </Text>
                </Box>
              )}

              <Button
                mt={4}
                colorScheme="brand"
                size="lg"
                w="full"
                onClick={handleUpload}
                isLoading={isUploading}
                loadingText="Uploading..."
              >
                Upload {files.length} file{files.length !== 1 ? 's' : ''}
              </Button>
            </CardBody>
          </Card>
        )}
      </VStack>
    </Box>
  );
};

export default Upload;
