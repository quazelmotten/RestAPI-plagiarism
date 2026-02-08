import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Box,
  Flex,
  Text,
  Button,
  Avatar,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  useColorModeValue,
} from '@chakra-ui/react';
import { FiChevronDown, FiLogOut } from 'react-icons/fi';

const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  return (
    <Box
      as="header"
      pos="fixed"
      top="0"
      left="250px"
      right="0"
      h="16"
      bg={bgColor}
      borderBottom="1px"
      borderColor={borderColor}
      px={8}
      zIndex="sticky"
    >
      <Flex h="full" align="center" justify="space-between">
        <Text fontSize="lg" fontWeight="semibold">
          Teacher Dashboard
        </Text>

        <Menu>
          <MenuButton
            as={Button}
            variant="ghost"
            rightIcon={<FiChevronDown />}
          >
            <Flex align="center">
              <Avatar size="sm" name={user?.username || 'User'} mr={2} />
              <Text>{user?.username || 'User'}</Text>
            </Flex>
          </MenuButton>
          <MenuList>
            <MenuItem icon={<FiLogOut />} onClick={logout}>
              Logout
            </MenuItem>
          </MenuList>
        </Menu>
      </Flex>
    </Box>
  );
};

export default Header;
