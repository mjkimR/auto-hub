import { create } from 'zustand';
import { client } from '../generated/api/client.gen';
import { getTaskSpecsApiV1TasksSpecsGet } from '../generated/api/sdk.gen';

interface AuthState {
  apiKey: string | null;
  isAuthenticated: boolean;
  isValidating: boolean;
  login: (key: string) => Promise<boolean>;
  logout: () => void;
  initializeAuth: () => void;
}

// Session storage key for persistent auth
const AUTH_KEY = 'scheduler-api-key';

export const useAuthStore = create<AuthState>((set, get) => ({
  apiKey: null,
  isAuthenticated: false,
  isValidating: false,

  login: async (key: string) => {
    set({ isValidating: true });

    // Temporarily set the key in state to test the request
    const originalKey = get().apiKey;
    set({ apiKey: key });

    try {
      // Try fetching a lightweight protected endpoint to test key validity
      const result = await getTaskSpecsApiV1TasksSpecsGet({ throwOnError: true });

      if (result && result.response && result.response.status === 200) {
        sessionStorage.setItem(AUTH_KEY, key);
        set({ isAuthenticated: true, isValidating: false });
        return true;
      }

      // If not successful status, rollback
      set({ apiKey: originalKey, isAuthenticated: !!originalKey, isValidating: false });
      return false;
    } catch {
      // Rollback on error
      set({ apiKey: originalKey, isAuthenticated: !!originalKey, isValidating: false });
      return false;
    }
  },

  logout: () => {
    sessionStorage.removeItem(AUTH_KEY);
    set({ apiKey: null, isAuthenticated: false });
  },

  initializeAuth: () => {
    const savedKey = sessionStorage.getItem(AUTH_KEY);
    if (savedKey) {
      set({ apiKey: savedKey, isAuthenticated: true });
    }
  },
}));

// Register interceptors once at module load
client.interceptors.request.use((request) => {
  const currentKey = useAuthStore.getState().apiKey || sessionStorage.getItem(AUTH_KEY);
  if (currentKey) {
    request.headers.set('X-API-Key', currentKey);
  }
  return request;
});

client.interceptors.error.use((error: any, response: any) => {
  const status = response?.status || error?.response?.status || error?.status;
  if (status === 401) {
    useAuthStore.getState().logout();
  }
  return Promise.reject(error);
});