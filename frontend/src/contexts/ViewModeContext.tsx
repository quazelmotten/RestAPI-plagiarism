import { createContext, useContext } from 'react';

export type ViewMode = 'assignments' | 'classic';

interface ViewModeContextValue {
  mode: ViewMode;
  setMode: (mode: ViewMode) => void;
}

export const ViewModeContext = createContext<ViewModeContextValue>({
  mode: 'assignments',
  setMode: () => {},
});

export const useViewMode = () => useContext(ViewModeContext);
