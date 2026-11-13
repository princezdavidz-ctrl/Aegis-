import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  createOidcSessionAdapter,
  OidcAuthenticationError,
  readOidcClientConfig,
  type OidcSession,
} from './oidc';

type AuthStatus = 'unconfigured' | 'checking' | 'anonymous' | 'authenticating' | 'authenticated' | 'error';

interface AuthContextValue {
  status: AuthStatus;
  session: OidcSession | null;
  error: string | null;
  signIn: (returnTo?: string) => Promise<void>;
  signOut: () => void;
}

const unavailableAuth: AuthContextValue = {
  status: 'unconfigured',
  session: null,
  error: null,
  signIn: async () => {},
  signOut: () => {},
};

const AuthContext = createContext<AuthContextValue>(unavailableAuth);

function safeError(error: unknown): string {
  return error instanceof OidcAuthenticationError
    ? error.message
    : 'Sign-in could not be completed. Please try again.';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const config = useMemo(() => {
    try {
      return {
        value: readOidcClientConfig({
          VITE_AEGIS_OIDC_ISSUER: import.meta.env.VITE_AEGIS_OIDC_ISSUER,
          VITE_AEGIS_OIDC_CLIENT_ID: import.meta.env.VITE_AEGIS_OIDC_CLIENT_ID,
          VITE_AEGIS_OIDC_REDIRECT_URI: import.meta.env.VITE_AEGIS_OIDC_REDIRECT_URI,
          VITE_AEGIS_OIDC_CLIENT_SECRET: import.meta.env.VITE_AEGIS_OIDC_CLIENT_SECRET,
        }, import.meta.env.DEV),
        error: null,
      };
    } catch {
      return { value: null, error: 'AEGIS sign-in configuration is invalid.' };
    }
  }, []);
  const adapterState = useMemo(() => {
    if (!config.value) return { value: null, error: null };
    try {
      return { value: createOidcSessionAdapter(config.value), error: null };
    } catch {
      return { value: null, error: 'AEGIS sign-in configuration is invalid.' };
    }
  }, [config]);
  const adapter = adapterState.value;
  const [session, setSession] = useState<OidcSession | null>(null);
  const callbackStarted = useRef(false);
  const [status, setStatus] = useState<AuthStatus>(
    config.error || adapterState.error ? 'error' : adapter ? 'checking' : 'unconfigured',
  );
  const [error, setError] = useState<string | null>(config.error ?? adapterState.error);

  useEffect(() => {
    if (!adapter || !config.value) return;
    const callbackPath = new URL(config.value.redirectUri).pathname;
    if (window.location.pathname !== callbackPath) {
      setStatus('anonymous');
      return;
    }

    if (callbackStarted.current) return;
    callbackStarted.current = true;
    setStatus('checking');
    adapter.completeSignIn(window.location.href)
      .then((result) => {
        setSession(result.session);
        setStatus('authenticated');
        window.history.replaceState(null, '', result.returnTo);
      })
      .catch((reason: unknown) => {
        adapter.signOut();
        setSession(null);
        setError(safeError(reason));
        setStatus('error');
        window.history.replaceState(null, '', '/');
      });

  }, [adapter, config]);

  const signIn = useCallback(async (returnTo = window.location.pathname) => {
    if (!adapter) {
      setStatus('unconfigured');
      return;
    }
    setError(null);
    setStatus('authenticating');
    try {
      await adapter.signIn({ returnTo });
    } catch (reason) {
      setError(safeError(reason));
      setStatus('error');
    }
  }, [adapter]);

  const signOut = useCallback(() => {
    adapter?.signOut();
    setSession(null);
    setError(null);
    setStatus(adapter ? 'anonymous' : 'unconfigured');
  }, [adapter]);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    session,
    error,
    signIn,
    signOut,
  }), [status, session, error, signIn, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
