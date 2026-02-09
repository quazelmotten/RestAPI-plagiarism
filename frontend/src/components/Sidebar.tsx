import React from 'react';
import { NavLink, useLocation } from 'react-router';
import {
  Box,
  VStack,
  Text,
  Icon,
  Flex,
  useColorModeValue,
} from '@chakra-ui/react';
import { FiHome, FiUsers, FiFileText, FiShare2, FiUpload, FiBarChart2, FiGitBranch } from 'react-icons/fi';

const menuItems = [
  { path: '/dashboard', label: 'Overview', icon: FiHome },
  { path: '/dashboard/students', label: 'Students', icon: FiUsers },
  { path: '/dashboard/submissions', label: 'Submissions', icon: FiFileText },
  { path: '/dashboard/graph', label: 'Plagiarism Graph', icon: FiShare2 },
  { path: '/dashboard/upload', label: 'Upload Files', icon: FiUpload },
  { path: '/dashboard/results', label: 'Results', icon: FiBarChart2 },
  { path: '/dashboard/compare', label: 'Compare Files', icon: FiGitBranch },
];

const Sidebar: React.FC = () => {
  const location = useLocation();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  return (
    <Box
      as="nav"
      pos="fixed"
      left="0"
      h="full"
      w="250px"
      bg={bgColor}
      borderRight="1px"
      borderColor={borderColor}
      py={6}
      px={4}
    >
      <Text fontSize="2xl" fontWeight="bold" mb={8} px={4}>
        Plagiarism Detection
      </Text>
      
      <VStack spacing={2} align="stretch">
        {menuItems.map((item) => (
          <NavLink key={item.path} to={item.path} style={{ textDecoration: 'none' }}>
            <Flex
              align="center"
              px={4}
              py={3}
              borderRadius="md"
              bg={location.pathname === item.path ? 'brand.500' : 'transparent'}
              color={location.pathname === item.path ? 'white' : 'inherit'}
              _hover={{
                bg: location.pathname === item.path ? 'brand.600' : useColorModeValue('gray.100', 'gray.700'),
              }}
              transition="all 0.2s"
            >
              <Icon as={item.icon} boxSize={5} mr={3} />
              <Text fontWeight="medium">{item.label}</Text>
            </Flex>
          </NavLink>
        ))}
      </VStack>
    </Box>
  );
};

export default Sidebar;
