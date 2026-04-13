import React, { useState } from 'react';
import { Box, Button, FormControl, FormLabel, Input, Heading, Alert, AlertIcon, VStack, Text } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';

const Profile: React.FC = () => {
  const { user, changePassword, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      setMessage('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    // redirect handled by interceptor
  };

  if (!user) return null;

  return (
    <Box maxW="md" mx="auto" mt={8} p={4}>
      <Heading mb={6}>Profile</Heading>
      <Text mb={4}>Email: {user.email}</Text>
      <form onSubmit={handleChangePassword}>
        <VStack spacing={4} align="stretch">
          <FormControl isRequired>
            <FormLabel>Current Password</FormLabel>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </FormControl>
          <FormControl isRequired>
            <FormLabel>New Password</FormLabel>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </FormControl>
          <Button type="submit" colorScheme="brand" isLoading={loading}>
            Change Password
          </Button>
        </VStack>
      </form>
      {error && (
        <Alert status="error" mt={4}>
          <AlertIcon />
          {error}
        </Alert>
      )}
      {message && (
        <Alert status="success" mt={4}>
          <AlertIcon />
          {message}
        </Alert>
      )}
      <Button mt={6} variant="outline" onClick={handleLogout} colorScheme="red">
        Logout
      </Button>
    </Box>
  );
};

export default Profile;
