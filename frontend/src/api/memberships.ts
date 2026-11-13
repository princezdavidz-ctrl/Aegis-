import type { TenantSession } from './tenantProfile';

export const ASSIGNABLE_MEMBER_ROLES = ['security_manager', 'analyst', 'viewer'] as const;
const MEMBER_ROLES = ['tenant_admin', ...ASSIGNABLE_MEMBER_ROLES] as const;
const MEMBER_STATUSES = ['pending', 'active', 'suspended', 'revoked'] as const;

export type AssignableMemberRole = (typeof ASSIGNABLE_MEMBER_ROLES)[number];
export type MemberRole = (typeof MEMBER_ROLES)[number];
export type MemberStatus = (typeof MEMBER_STATUSES)[number];
export type MembershipAction = 'change_role' | 'suspend' | 'revoke';

export interface MembershipSession extends TenantSession {
  /** Display-only role hint from a trusted, server-verified membership bootstrap. */
  membershipRole: string;
  /** Verified OIDC subject, used only to suppress self-management controls. */
  subject: string;
}

export interface TenantMember {
  id: string;
  subject: string;
  role: MemberRole;
  status: MemberStatus;
  created_at: string;
  invitation_expires_at: string | null;
}

export interface MemberActionResult {
  id: string;
  subject: string;
  role: MemberRole;
  status: MemberStatus;
}

export interface MemberInviteInput {
  subject: string;
  role: AssignableMemberRole;
}

export type MemberUpdateInput =
  | { action: 'change_role'; role: AssignableMemberRole }
  | { action: 'suspend' | 'revoke' };

type FetchImplementation = typeof fetch;

export class MembershipApiError extends Error {
  readonly status: number;
  readonly code: 'request_failed' | 'invalid_response';

  constructor(status: number, code: 'request_failed' | 'invalid_response' = 'request_failed') {
    super(code === 'invalid_response'
      ? 'The membership service returned an invalid response.'
      : 'The membership request failed.');
    this.name = 'MembershipApiError';
    this.status = status;
    this.code = code;
  }
}

const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/;

function normalizeBaseUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new TypeError('A valid AEGIS API base URL is required.');
  }

  const isLoopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  const secureTransport = url.protocol === 'https:' || (url.protocol === 'http:' && isLoopback);

  if (
    !secureTransport ||
    url.username.length > 0 ||
    url.password.length > 0 ||
    url.search.length > 0 ||
    url.hash.length > 0 ||
    (url.pathname !== '' && url.pathname !== '/')
  ) {
    throw new TypeError('The AEGIS API base URL must be an HTTPS origin (HTTP is allowed only for loopback development).');
  }

  return url.origin;
}

function normalizeSession(session: TenantSession): { accessToken: string; tenantSlug: string } {
  if (typeof session.accessToken !== 'string' || typeof session.tenantSlug !== 'string') {
    throw new TypeError('A verified tenant session is required.');
  }

  const accessToken = session.accessToken.trim();
  const tenantSlug = session.tenantSlug.trim();

  if (accessToken.length === 0 || accessToken.length > 8192) {
    throw new TypeError('A valid short-lived access token is required.');
  }
  if (!TENANT_SLUG_PATTERN.test(tenantSlug)) {
    throw new TypeError('A valid tenant slug is required.');
  }

  return { accessToken, tenantSlug };
}

function normalizeSubject(value: string): string {
  if (typeof value !== 'string') {
    throw new TypeError('A valid identity subject is required.');
  }
  const subject = value.trim();
  if (!subject || subject.length > 128 || CONTROL_CHARACTERS.test(subject)) {
    throw new TypeError('Identity subject must contain 1 to 128 printable characters.');
  }
  return subject;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isOneOf<const T extends readonly string[]>(values: T, value: unknown): value is T[number] {
  return typeof value === 'string' && (values as readonly string[]).includes(value);
}

function isMember(value: unknown): value is TenantMember {
  if (!isRecord(value)) return false;
  const allowedKeys = new Set([
    'id', 'subject', 'role', 'status', 'created_at', 'invitation_expires_at',
  ]);
  if (Object.keys(value).some((key) => !allowedKeys.has(key))) return false;

  return (
    typeof value.id === 'string' && UUID_PATTERN.test(value.id) &&
    typeof value.subject === 'string' && value.subject.trim().length > 0 &&
    value.subject.length <= 128 && !CONTROL_CHARACTERS.test(value.subject) &&
    isOneOf(MEMBER_ROLES, value.role) &&
    isOneOf(MEMBER_STATUSES, value.status) &&
    typeof value.created_at === 'string' && Number.isFinite(Date.parse(value.created_at)) &&
    (value.invitation_expires_at === null ||
      (typeof value.invitation_expires_at === 'string' && Number.isFinite(Date.parse(value.invitation_expires_at))))
  );
}

function isMemberList(value: unknown): value is TenantMember[] {
  return Array.isArray(value) && value.every(isMember);
}

function isMemberActionResult(value: unknown): value is MemberActionResult {
  if (!isRecord(value)) return false;
  const allowedKeys = new Set(['id', 'subject', 'role', 'status']);
  if (Object.keys(value).some((key) => !allowedKeys.has(key))) return false;

  return (
    typeof value.id === 'string' && UUID_PATTERN.test(value.id) &&
    typeof value.subject === 'string' && value.subject.trim().length > 0 &&
    value.subject.length <= 128 && !CONTROL_CHARACTERS.test(value.subject) &&
    isOneOf(MEMBER_ROLES, value.role) &&
    isOneOf(MEMBER_STATUSES, value.status)
  );
}

function normalizeInvite(input: MemberInviteInput): MemberInviteInput {
  if (!isRecord(input) || Object.keys(input).some((key) => !['subject', 'role'].includes(key))) {
    throw new TypeError('Only an identity subject and assignable role may be submitted.');
  }
  const subject = normalizeSubject(input.subject);
  if (!isOneOf(ASSIGNABLE_MEMBER_ROLES, input.role)) {
    throw new TypeError('A supported non-administrator member role is required.');
  }
  return { subject, role: input.role };
}

function normalizeUpdate(input: MemberUpdateInput): MemberUpdateInput {
  if (!isRecord(input) || !isOneOf(['change_role', 'suspend', 'revoke'] as const, input.action)) {
    throw new TypeError('Unsupported membership action.');
  }

  if (input.action === 'change_role') {
    if (Object.keys(input).some((key) => !['action', 'role'].includes(key)) ||
        !isOneOf(ASSIGNABLE_MEMBER_ROLES, input.role)) {
      throw new TypeError('A supported role is required for a role change.');
    }
    return { action: 'change_role', role: input.role };
  }

  if (Object.keys(input).some((key) => key !== 'action')) {
    throw new TypeError('A role is not accepted for suspend or revoke actions.');
  }
  return { action: input.action };
}

export function createMembershipClient(
  baseUrl: string,
  fetchImplementation: FetchImplementation = fetch,
) {
  const apiBaseUrl = normalizeBaseUrl(baseUrl);

  async function request(path: string, session: TenantSession, init: RequestInit = {}): Promise<unknown> {
    const identity = normalizeSession(session);
    const response = await fetchImplementation(apiBaseUrl + path, {
      ...init,
      headers: {
        Accept: 'application/json',
        Authorization: 'Bearer ' + identity.accessToken,
        'X-AEGIS-Tenant': identity.tenantSlug,
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      },
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      referrerPolicy: 'no-referrer',
    });

    if (!response.ok) throw new MembershipApiError(response.status);

    try {
      return await response.json();
    } catch {
      throw new MembershipApiError(response.status, 'invalid_response');
    }
  }

  return Object.freeze({
    async listMembers(session: TenantSession): Promise<TenantMember[]> {
      const payload = await request('/api/v1/tenants/members', session, { method: 'GET' });
      if (!isMemberList(payload)) throw new MembershipApiError(200, 'invalid_response');
      return payload;
    },

    async inviteMember(session: TenantSession, input: MemberInviteInput): Promise<MemberActionResult> {
      const invite = normalizeInvite(input);
      const payload = await request('/api/v1/tenants/members/invitations', session, {
        method: 'POST',
        body: JSON.stringify(invite),
      });
      if (!isMemberActionResult(payload)) throw new MembershipApiError(201, 'invalid_response');
      return payload;
    },

    async updateMember(
      session: TenantSession,
      subjectValue: string,
      input: MemberUpdateInput,
    ): Promise<MemberActionResult> {
      const subject = normalizeSubject(subjectValue);
      const update = normalizeUpdate(input);
      const payload = await request('/api/v1/tenants/members/' + encodeURIComponent(subject), session, {
        method: 'PATCH',
        body: JSON.stringify(update),
      });
      if (!isMemberActionResult(payload)) throw new MembershipApiError(200, 'invalid_response');
      return payload;
    },
  });
}
