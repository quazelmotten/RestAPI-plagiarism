import React, { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import { Box, Button, FormControl, FormLabel, Input, Heading, Alert, AlertIcon, VStack } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';

const ResetPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [newPassword, setNewPassword] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { resetPassword } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      await resetPassword(token, newPassword);
      setMessage('Password reset successful. You can now log in.');
      setTimeout(() => navigate('/login'), 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Reset failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box maxW="md" mx="auto" mt={8} p={4}>
      <Heading mb={6}>Reset Password</Heading>
      {error && (
        <Alert status="error" mb={4}>
          <AlertIcon />
          {error}
        </Alert>
      )}
      {message && (
        <Alert status="success" mb={4}>
          <AlertIcon />
          {message}
        </Alert>
      )}
      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch">
          <FormControl isRequired>
            <FormLabel>New Password</FormLabel>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </FormControl>
          <Button type="submit" colorScheme="brand" isLoading={loading}>
            Reset Password
          </Button>
        </VStack>
      </form>
    </Box>
  );
};

export default ResetPassword;
