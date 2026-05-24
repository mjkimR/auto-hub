import { create } from 'zustand';

interface ThemeState {
  isDarkMode: boolean;
  activeTab: string;
  triggerLoading: boolean;
  preselectedTask: string | null;
  toggleDarkMode: () => void;
  setActiveTab: (tab: string) => void;
  setTriggerLoading: (loading: boolean) => void;
  setPreselectedTask: (task: string | null) => void;
}

export const useThemeStore = create<ThemeState>((set) => {
  // Check if dark mode is preferred by system or saved in localStorage
  const savedTheme = localStorage.getItem('scheduler-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialDark = savedTheme ? savedTheme === 'dark' : prefersDark;

  // Apply initial theme class to HTML body
  if (initialDark) {
    document.documentElement.classList.add('dark-theme');
  } else {
    document.documentElement.classList.remove('dark-theme');
  }

  return {
    isDarkMode: initialDark,
    activeTab: 'dashboard',
    triggerLoading: false,
    preselectedTask: null,
    toggleDarkMode: () =>
      set((state) => {
        const nextDark = !state.isDarkMode;
        localStorage.setItem('scheduler-theme', nextDark ? 'dark' : 'light');
        if (nextDark) {
          document.documentElement.classList.add('dark-theme');
        } else {
          document.documentElement.classList.remove('dark-theme');
        }
        return { isDarkMode: nextDark };
      }),
    setActiveTab: (tab) => set({ activeTab: tab }),
    setTriggerLoading: (loading) => set({ triggerLoading: loading }),
    setPreselectedTask: (task) => set({ preselectedTask: task }),
  };
});
