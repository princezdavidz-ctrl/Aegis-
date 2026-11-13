import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
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
      return { value: readOidcClientConfig(import.meta.env, import.meta.env.DEV), error: null };
    } catch {
      return { value: null, error: 'AEGIS sign-in configuration is invalid.' };
    }
  }, []);
  const adapter = useMemo(() => {
    if (!config.value) return null;
    try {
      return createOidcSessionAdapter(config.value);
    } catch {
      return null;
    }
  }, [config]);
  const [session, setSession] = useState<OidcSession | null>(null);
  const [status, setStatus] = useState<AuthStatus>(
    config.error ? 'error' : adapter ? 'checking' : 'unconfigured',
  );
  const [error, setError] = useState<string | null>(config.error);

  useEffect(() => {
    if (!adapter || !config.value) return;
    const callbackPath = new URL(config.value.redirectUri).pathname;
    if (window.location.pathname !== callbackPath) {
      setStatus('anonymous');
      return;
    }

    let active = true;
    setStatus('checking');
    adapter.completeSignIn(window.location.href)
      .then((result) => {
        if (!active) return;
        setSession(result.session);
        setStatus('authenticated');
        window.history.replaceState(null, '', result.returnTo);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        adapter.signOut();
        setSession(null);
        setError(safeError(reason));
        setStatus('error');
        window.history.replaceState(null, '', '/');
      });

    return () => {
      active = false;
    };
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
