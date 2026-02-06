import React, { useState } from 'react';
import {
  Box,
  Heading,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Input,
  InputGroup,
  InputLeftElement,
  Button,
  Flex,
  Card,
  CardBody,
  Badge,
} from '@chakra-ui/react';
import { FiSearch, FiPlus } from 'react-icons/fi';

const Students: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  
  // Placeholder data - will be replaced with API call
  const students: any[] = [];

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading>Students</Heading>
        <Button leftIcon={<FiPlus />} colorScheme="brand">
          Add Student
        </Button>
      </Flex>

      <Card>
        <CardBody>
          <Flex mb={4}>
            <InputGroup maxW="400px">
              <InputLeftElement pointerEvents="none">
                <FiSearch />
              </InputLeftElement>
              <Input
                placeholder="Search students..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </InputGroup>
          </Flex>

          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Email</Th>
                <Th>Submissions</Th>
                <Th>Status</Th>
              </Tr>
            </Thead>
            <Tbody>
              {students.length === 0 ? (
                <Tr>
                  <Td colSpan={4} textAlign="center" py={8}>
                    No students found
                  </Td>
                </Tr>
              ) : (
                students.map((student: any) => (
                  <Tr key={student.id}>
                    <Td>{student.fullName}</Td>
                    <Td>{student.email}</Td>
                    <Td>{student.submissionsCount}</Td>
                    <Td>
                      <Badge colorScheme="green">Active</Badge>
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

export default Students;
