import React from 'react';
import { Card, CardBody, Tabs, TabList, Tab } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';

interface ReviewTabsProps {
  activeTab: number;
  setActiveTab: (tab: number) => void;
  unreviewedCount: number;
  totalCount: number;
  confirmedCount: number;
  bulkConfirmedCount: number;
  clearedCount: number;
}

export const ReviewTabs: React.FC<ReviewTabsProps> = ({
  activeTab,
  setActiveTab,
  unreviewedCount,
  totalCount,
  confirmedCount,
  bulkConfirmedCount,
  clearedCount,
}) => {
  const { t } = useTranslation(['common', 'review']);

  return (
    <Card>
      <CardBody py={2}>
        <Tabs variant="soft-rounded" colorScheme="blue" onChange={setActiveTab}>
          <TabList>
            <Tab>{t('review:toReview')} ({unreviewedCount})</Tab>
            <Tab>{t('review:allPairs')} ({totalCount})</Tab>
            <Tab>{t('review:confirmed')} ({confirmedCount})</Tab>
            <Tab>{t('review:bulkConfirmed')} ({bulkConfirmedCount})</Tab>
            <Tab>{t('review:cleared')} ({clearedCount})</Tab>
          </TabList>
        </Tabs>
      </CardBody>
    </Card>
  );
};