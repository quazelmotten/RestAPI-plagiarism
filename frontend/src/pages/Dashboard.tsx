import React from 'react';
import { Routes, Route, Navigate } from 'react-router';
import {
  Box,
  Flex,
  useColorModeValue,
} from '@chakra-ui/react';
import Sidebar from '../components/Sidebar';
import { SidebarProvider } from '../contexts/SidebarContext';
import Header from '../components/Header';
import { AssignmentProvider } from '../contexts/AssignmentContext';
import { SIDEBAR_WIDTH_PX } from '../constants/layout';
import Overview from './Overview';
import Assignments from './Assignments';
import AssignmentDetail from './AssignmentDetail';
import PairComparison from './PairComparison';
import Settings from './Settings';
import Storage from './Storage';
import Files from './Files';
import UploadDetail from './UploadDetail';
import Review from './Review';
import QuickCheck from './QuickCheck';
import Users from './Users';
import Admin from './Admin';
import Events from './Events';

const Dashboard: React.FC = () => {
  return (
    <AssignmentProvider>
      <SidebarProvider>
        <Flex h="100vh" bg={useColorModeValue('gray.100', 'gray.900')}>
          <Sidebar />
          <Box flex="1" ml={{ base: 0, lg: SIDEBAR_WIDTH_PX }} display="flex" flexDirection="column" overflow="hidden">
            <Header />
            <Box as="main" p={8} pt={24} flex="1" overflow="hidden" minH={0} display="flex" flexDirection="column">
                <Routes>
                  <Route path="/" element={<Overview />} />
                  <Route path="files" element={<Files />} />
                  <Route path="uploads/:uploadId" element={<UploadDetail />} />
                  <Route path="review" element={<Review />} />
                  <Route path="quick-check" element={<QuickCheck />} />
                  <Route path="assignments" element={<Assignments />} />
                  <Route path="assignments/:assignmentId" element={<AssignmentDetail />} />
                  <Route path="pair-comparison" element={<PairComparison />} />
                  <Route path="settings" element={<Settings />} />
                  <Route path="storage" element={<Navigate to="/dashboard/admin/storage" replace />} />
                  <Route path="users" element={<Navigate to="/dashboard/admin/users" replace />} />
                  <Route path="admin/stats" element={<Admin />} />
                  <Route path="admin/storage" element={<Admin initialTab={1} />} />
                  <Route path="admin/users" element={<Admin initialTab={2} />} />
                  <Route path="admin/api-keys" element={<Admin initialTab={3} />} />
                  <Route path="events" element={<Events />} />
                </Routes>
            </Box>
          </Box>
        </Flex>
      </SidebarProvider>
    </AssignmentProvider>
  );
};

export default Dashboard;
