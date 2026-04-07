import { ChakraProvider, extendTheme, ColorModeScript } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router';
import Dashboard from './pages/Dashboard';
import { getBasePath } from './utils/subpath';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const getColorMode = (): 'light' | 'dark' => {
  try {
    return (localStorage.getItem('chakra-ui-color-mode') as 'light' | 'dark') || 'light';
  } catch {
    return 'light';
  }
};

const theme = extendTheme({
  config: {
    initialColorMode: getColorMode(),
    useSystemColorMode: false,
  },
  colors: {
    brand: {
      50: '#e6f7ff',
      100: '#b3e0ff',
      200: '#80caff',
      300: '#4db4ff',
      400: '#269eff',
      500: '#1890ff',
      600: '#096dd9',
      700: '#0050b3',
      800: '#003a8c',
      900: '#002766',
    },
  },
});

const BASE = getBasePath();

function App() {
  return (
    <>
      <ColorModeScript initialColorMode={theme.config.initialColorMode} />
      <ChakraProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <Router basename={BASE}>
            <Routes>
              <Route path="/dashboard/*" element={<Dashboard />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Router>
        </QueryClientProvider>
      </ChakraProvider>
    </>
  );
}

export default App;
