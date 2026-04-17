import React, { useState } from 'react';
import { Box, Button, FormControl, FormLabel, Input, Heading, Alert, AlertIcon, VStack } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { forgotPassword } = useAuth();
  const { t } = useTranslation();

    const navigate = useNavigate();
    const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      await forgotPassword(email);
      setMessage(t('resetLinkSent'));
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || t('requestFailed'));
    } finally {
      setLoading(false);
    }
  };


  return (
    <Box maxW="md" mx="auto" mt={8} p={4}>
      <Heading mb={6}>{t('forgotPassword')}</Heading>
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
            <FormLabel>{t('email')}</FormLabel>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </FormControl>
          <Button type="submit" colorScheme="brand" isLoading={loading}>
            {t('sendResetLink')}
          </Button>
        </VStack>
      </form>
    </Box>
  );
};

export default ForgotPassword;
