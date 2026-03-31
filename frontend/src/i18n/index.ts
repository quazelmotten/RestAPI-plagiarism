import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enCommon from '../locales/en/common.json';
import enNavigation from '../locales/en/navigation.json';
import enUpload from '../locales/en/upload.json';
import enAssignments from '../locales/en/assignments.json';
import enSubmissions from '../locales/en/submissions.json';
import enResults from '../locales/en/results.json';
import enGraph from '../locales/en/graph.json';
import enPairComparison from '../locales/en/pair-comparison.json';
import enOverview from '../locales/en/overview.json';
import enStatus from '../locales/en/status.json';
import enLanguages from '../locales/en/languages.json';

import ruCommon from '../locales/ru/common.json';
import ruNavigation from '../locales/ru/navigation.json';
import ruUpload from '../locales/ru/upload.json';
import ruAssignments from '../locales/ru/assignments.json';
import ruSubmissions from '../locales/ru/submissions.json';
import ruResults from '../locales/ru/results.json';
import ruGraph from '../locales/ru/graph.json';
import ruPairComparison from '../locales/ru/pair-comparison.json';
import ruOverview from '../locales/ru/overview.json';
import ruStatus from '../locales/ru/status.json';
import ruLanguages from '../locales/ru/languages.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: enCommon,
        navigation: enNavigation,
        upload: enUpload,
        assignments: enAssignments,
        submissions: enSubmissions,
        results: enResults,
        graph: enGraph,
        pairComparison: enPairComparison,
        overview: enOverview,
        status: enStatus,
        languages: enLanguages,
      },
      ru: {
        common: ruCommon,
        navigation: ruNavigation,
        upload: ruUpload,
        assignments: ruAssignments,
        submissions: ruSubmissions,
        results: ruResults,
        graph: ruGraph,
        pairComparison: ruPairComparison,
        overview: ruOverview,
        status: ruStatus,
        languages: ruLanguages,
      },
    },
    lng: localStorage.getItem('language') || 'en',
    fallbackLng: 'en',
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
