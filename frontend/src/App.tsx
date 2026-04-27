import { ChakraProvider, extendTheme, ColorModeScript, CSSReset } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Profile from './pages/Profile';
import Users from './pages/Users';
import { getBasePath } from './utils/subpath';
import { isAuthenticated } from './services/api';
import { AuthProvider, useAuth } from './contexts/AuthContext';

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
    initialColorMode: 'system',
    useSystemColorMode: true,
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
  styles: {
    global: (props: { colorMode: string }) => ({
      body: {
        bg: props.colorMode === 'dark' ? 'gray.800' : 'white',
        color: props.colorMode === 'dark' ? 'white' : 'gray.800',
      },
    }),
  },
  components: {
    Tabs: {
      variants: {
        'soft-rounded': {
          tab: {
            color: 'gray.600',
            _selected: {
              color: 'white',
              bg: 'blue.500',
            },
            _dark: {
              color: 'gray.300',
              _selected: {
                color: 'white',
                bg: 'blue.400',
              },
            },
          },
        },
      },
    },
    Card: {
      baseStyle: (props: { colorMode: string }) => ({
        container: {
          bg: props.colorMode === 'dark' ? 'gray.700' : 'white',
        },
      }),
    },
  },
});

const BASE = getBasePath();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  if (!user?.is_global_admin) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}

function App() {
  return (
    <>
      <ColorModeScript initialColorMode="system" />
      <CSSReset />
      <ChakraProvider theme={theme}>
<QueryClientProvider client={queryClient}>
            <AuthProvider>
              <Router basename={BASE}>
                <Routes>
                  <Route path="/login" element={<Login />} />
                  <Route path="/forgot-password" element={<ForgotPassword />} />
                  <Route path="/reset-password" element={<ResetPassword />} />
                  <Route
                    path="/dashboard/*"
                    element={
                      <ProtectedRoute>
                        <Dashboard />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/profile"
                    element={
                      <ProtectedRoute>
                        <Profile />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/dashboard/users"
                    element={
                      <AdminRoute>
                        <Users />
                      </AdminRoute>
                    }
                  />
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </Router>
            </AuthProvider>
          </QueryClientProvider>
      </ChakraProvider>
    </>
  );
}

export default App;
