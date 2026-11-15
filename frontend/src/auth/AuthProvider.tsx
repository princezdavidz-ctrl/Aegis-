import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  createMembershipBootstrapClient,
  MembershipBootstrapApiError,
  type ActiveTenantMembership,
} from '../api/membershipBootstrap';
import type { TenantSession } from '../api/tenantProfile';
import {
  createOidcSessionAdapter,
  OidcAuthenticationError,
  readOidcClientConfig,
  type OidcSession,
} from './oidc';

type AuthStatus = 'unconfigured' | 'checking' | 'anonymous' | 'authenticating' | 'authenticated' | 'error';

interface AuthContextValue {
  configured: boolean;
  status: AuthStatus;
  session: OidcSession | null;
  membershipStatus: 'unconfigured' | 'loading' | 'ready' | 'error';
  membershipError: string | null;
  memberships: ActiveTenantMembership[];
  selectedMembership: ActiveTenantMembership | null;
  tenantSession: (TenantSession & { membershipRole: string; subject: string }) | null;
  selectTenant: (tenantSlug: string) => void;
  error: string | null;
  signIn: (returnTo?: string) => Promise<void>;
  signOut: () => void;
}

const unavailableAuth: AuthContextValue = {
  configured: false,
  status: 'unconfigured',
  session: null,
  membershipStatus: 'unconfigured',
  membershipError: null,
  memberships: [],
  selectedMembership: null,
  tenantSession: null,
  selectTenant: () => {},
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
  const membershipClientState = useMemo(() => {
    const apiBaseUrl = import.meta.env.VITE_AEGIS_API_BASE_URL?.trim() ?? '';
    if (!apiBaseUrl) return { client: null, error: 'AEGIS API connection is not configured.' };
    try {
      return { client: createMembershipBootstrapClient(apiBaseUrl), error: null };
    } catch {
      return { client: null, error: 'AEGIS API configuration is invalid.' };
    }
  }, []);
  const [session, setSession] = useState<OidcSession | null>(null);
  const [memberships, setMemberships] = useState<ActiveTenantMembership[]>([]);
  const [membershipSession, setMembershipSession] = useState<OidcSession | null>(null);
  const [selectedTenantSlug, setSelectedTenantSlug] = useState<string | null>(null);
  const [membershipStatus, setMembershipStatus] = useState<'unconfigured' | 'loading' | 'ready' | 'error'>('unconfigured');
  const [membershipError, setMembershipError] = useState<string | null>(null);
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

  useEffect(() => {
    if (!session) {
      setMemberships([]);
      setMembershipSession(null);
      setSelectedTenantSlug(null);
      setMembershipStatus('unconfigured');
      setMembershipError(null);
      return;
    }

    const client = membershipClientState.client;
    if (!client) {
      setMemberships([]);
      setMembershipSession(null);
      setSelectedTenantSlug(null);
      setMembershipStatus('error');
      setMembershipError(membershipClientState.error ?? 'AEGIS API connection is not available.');
      return;
    }

    let active = true;
    setMemberships([]);
    setMembershipSession(null);
    setMembershipStatus('loading');
    setMembershipError(null);

    client.listMyMemberships(session.accessToken)
      .then((result) => {
        if (!active) return;
        setMemberships(result);
        setSelectedTenantSlug((current) =>
          result.some((membership) => membership.tenant_slug === current)
            ? current
            : result[0]?.tenant_slug ?? null,
        );
        setMembershipSession(session);
        setMembershipStatus('ready');
        setMembershipError(result.length === 0
          ? 'No active organization memberships are assigned to this identity.'
          : null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setMemberships([]);
        setMembershipSession(null);
        setSelectedTenantSlug(null);
        setMembershipStatus('error');
        setMembershipError(
          reason instanceof MembershipBootstrapApiError && reason.status === 401
            ? 'The API rejected this access token. Verify the API audience and sign in again.'
            : 'Active organization access could not be loaded. Check the API connection and try again.',
        );
      });

    return () => {
      active = false;
    };
  }, [session, membershipClientState]);

  useEffect(() => {
    if (!session || !adapter) return;
    // The adapter applies its configured clock skew; expire UI state at the same boundary.
    const expiresIn = Math.max(0, session.expiresAt * 1000 - Date.now() - 60_000);
    const timeout = window.setTimeout(() => {
      if (!adapter.getSession()) {
        setSession(null);
        setStatus('anonymous');
        setError('Your sign-in session expired. Sign in again to continue.');
      }
    }, expiresIn);
    return () => window.clearTimeout(timeout);
  }, [session, adapter]);

  const selectTenant = useCallback((tenantSlug: string) => {
    if (membershipSession !== session || membershipStatus !== 'ready') return;
    if (!memberships.some((membership) => membership.tenant_slug === tenantSlug)) return;
    setSelectedTenantSlug(tenantSlug);
  }, [memberships, membershipSession, membershipStatus, session]);

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
    setMemberships([]);
    setMembershipSession(null);
    setSelectedTenantSlug(null);
    setMembershipStatus('unconfigured');
    setMembershipError(null);
    setError(null);
    setStatus(adapter ? 'anonymous' : 'unconfigured');
  }, [adapter]);

  const resolvedMemberships = membershipSession === session && membershipStatus === 'ready'
    ? memberships
    : [];
  const selectedMembership = resolvedMemberships.find(
    (membership) => membership.tenant_slug === selectedTenantSlug,
  ) ?? null;
  const tenantSession = useMemo(() => {
    if (!session || !selectedMembership) return null;
    return {
      accessToken: session.accessToken,
      tenantSlug: selectedMembership.tenant_slug,
      membershipRole: selectedMembership.role,
      subject: session.subject,
    };
  }, [session, selectedMembership]);

  const value = useMemo<AuthContextValue>(() => ({
    configured: adapter !== null,
    status,
    session,
    membershipStatus,
    membershipError,
    memberships: resolvedMemberships,
    selectedMembership,
    tenantSession,
    selectTenant,
    error,
    signIn,
    signOut,
  }), [
    adapter, status, session, membershipStatus, membershipError, resolvedMemberships,
    selectedMembership, tenantSession, selectTenant, error, signIn, signOut,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
