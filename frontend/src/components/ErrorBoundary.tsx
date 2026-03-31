import React, { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { Box, Button, Heading, Text, VStack } from '@chakra-ui/react';
import { withTranslation, type WithTranslation } from 'react-i18next';

interface ErrorBoundaryProps extends WithTranslation {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    } else {
      console.error('Uncaught error:', error, errorInfo);
    }
  }

  resetError = (): void => {
    this.setState({ hasError: false, error: undefined });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Box p={6} bg="red.50" borderWidth={1} borderColor="red.200" borderRadius="md">
          <VStack spacing={4} align="stretch">
            <Heading size="md" color="red.600">
              {this.props.t('common:somethingWentWrong')}
            </Heading>
            <Text color="red.700">
              {this.state.error?.message || this.props.t('common:unexpectedError')}
            </Text>
            <Button
              alignSelf="flex-start"
              colorScheme="red"
              onClick={this.resetError}
            >
              {this.props.t('common:retry')}
            </Button>
          </VStack>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default withTranslation('common')(ErrorBoundary);