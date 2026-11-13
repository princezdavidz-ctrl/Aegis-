import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import {
  AlertCircle,
  Check,
  Clock3,
  RefreshCw,
  ShieldCheck,
  UserPlus,
  UserRoundX,
  Users,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
  ASSIGNABLE_MEMBER_ROLES,
  MembershipApiError,
  createMembershipClient,
  type AssignableMemberRole,
  type MemberRole,
  type MemberStatus,
  type MembershipSession,
  type TenantMember,
} from '../api/memberships';

interface MembershipPageProps {
  /** Supplied only by a trusted OIDC session and server-resolved membership bootstrap. */
  session?: MembershipSession;
}

const apiBaseUrl = import.meta.env.VITE_AEGIS_API_BASE_URL?.trim() ?? '';

function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function statusClass(status: MemberStatus): string {
  if (status === 'active') return 'border-emerald-300/20 bg-emerald-300/[0.08] text-emerald-200';
  if (status === 'pending') return 'border-amber-300/20 bg-amber-300/[0.08] text-amber-200';
  if (status === 'suspended') return 'border-orange-300/20 bg-orange-300/[0.08] text-orange-200';
  return 'border-slate-400/20 bg-slate-400/[0.08] text-slate-400';
}

function isAssignableRole(value: MemberRole): value is AssignableMemberRole {
  return (ASSIGNABLE_MEMBER_ROLES as readonly string[]).includes(value);
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof MembershipApiError && error.status === 401) {
    return 'Your session is not valid. Sign in again before managing members.';
  }
  if (error instanceof MembershipApiError && error.status === 403) {
    return 'Tenant administrator access is required, or your membership has changed.';
  }
  if (error instanceof MembershipApiError && error.status === 409) {
    return 'The membership change conflicts with existing organization state. The subject may already have a membership, or the last active administrator is protected.';
  }
  return 'The membership service is unavailable. Check the connection and try again.';
}

function StatePanel({
  title,
  description,
  icon: Icon = Users,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
}) {
  return (
    <section aria-labelledby="members-heading" className="mx-auto flex min-h-[420px] max-w-3xl flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-[#101722] p-8 text-center">
      <span className="grid size-12 place-items-center rounded-2xl border border-cyan-200/15 bg-cyan-300/[0.07] text-cyan-200">
        <Icon size={23} aria-hidden="true" />
      </span>
      <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-200">Organization access</p>
      <h2 id="members-heading" className="mt-3 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">{description}</p>
    </section>
  );
}

function MemberStatusLabel({ status }: { status: MemberStatus }) {
  return (
    <span className={'inline-flex rounded-full border px-2.5 py-1 text-[10px] ' + statusClass(status)}>
      {status === 'pending' ? 'Pending invite' : humanize(status)}
    </span>
  );
}

export function MembershipPage({ session }: MembershipPageProps) {
  const clientConfig = useMemo(() => {
    if (!apiBaseUrl) return { state: 'missing' as const };
    try {
      return { state: 'ready' as const, client: createMembershipClient(apiBaseUrl) };
    } catch {
      return { state: 'invalid' as const };
    }
  }, []);

  const hasVerifiedSubject = typeof session?.subject === 'string' && session.subject.trim().length > 0;
  const canManage = session?.membershipRole === 'tenant_admin' && hasVerifiedSubject;
  const contextKey = session ? JSON.stringify([session.tenantSlug, session.subject]) : null;

  const [members, setMembers] = useState<TenantMember[]>([]);
  const [loadedContext, setLoadedContext] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [inviteSubject, setInviteSubject] = useState('');
  const [inviteRole, setInviteRole] = useState<AssignableMemberRole>('viewer');
  const [savingInvite, setSavingInvite] = useState(false);
  const [selectedRoles, setSelectedRoles] = useState<Record<string, MemberRole>>({});
  const [busySubject, setBusySubject] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{ subject: string; action: 'suspend' | 'revoke'; contextKey: string } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    if (!session || !canManage || clientConfig.state !== 'ready' || !contextKey) {
      setMembers([]);
      setLoadedContext(null);
      setPendingAction(null);
      setSelectedRoles({});
      setBusySubject(null);
      setFeedback(null);
      setInviteSubject('');
      setLoading(false);
      return;
    }

    let active = true;
    setMembers([]);
    setLoadedContext(null);
    setLoading(true);
    setError(null);

    clientConfig.client.listMembers(session)
      .then((result) => {
        if (active) {
          setMembers(result);
          setLoadedContext(contextKey);
          setSelectedRoles({});
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(requestErrorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [session, canManage, clientConfig, contextKey, retryCount]);

  useEffect(() => {
    setPendingAction(null);
    setSelectedRoles({});
    setBusySubject(null);
    setFeedback(null);
    setInviteSubject('');
  }, [contextKey]);

  async function inviteMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !canManage || clientConfig.state !== 'ready') return;

    const subject = inviteSubject.trim();
    if (subject === session.subject) {
      setFeedback({ kind: 'error', message: 'You cannot invite your own identity subject.' });
      return;
    }

    setSavingInvite(true);
    setFeedback(null);
    try {
      await clientConfig.client.inviteMember(session, { subject, role: inviteRole });
      setInviteSubject('');
      setFeedback({ kind: 'success', message: 'Pending membership created. No email or identity-provider account was created.' });
      setRetryCount((value) => value + 1);
    } catch (reason: unknown) {
      setFeedback({ kind: 'error', message: requestErrorMessage(reason) });
    } finally {
      setSavingInvite(false);
    }
  }

  async function changeMemberRole(member: TenantMember) {
    if (!session || !canManage || clientConfig.state !== 'ready') return;
    const nextRole = selectedRoles[member.id] ?? member.role;
    if (!isAssignableRole(nextRole) || nextRole === member.role) return;

    setBusySubject(member.subject);
    setFeedback(null);
    try {
      await clientConfig.client.updateMember(session, member.subject, {
        action: 'change_role',
        role: nextRole,
      });
      setFeedback({ kind: 'success', message: 'Member role updated and audited.' });
      setRetryCount((value) => value + 1);
    } catch (reason: unknown) {
      setFeedback({ kind: 'error', message: requestErrorMessage(reason) });
    } finally {
      setBusySubject(null);
    }
  }

  async function confirmMemberAction() {
    if (!session || !canManage || clientConfig.state !== 'ready' || !pendingAction || pendingAction.contextKey !== contextKey) return;

    const action = pendingAction.action;
    setConfirming(true);
    setBusySubject(pendingAction.subject);
    setFeedback(null);
    try {
      await clientConfig.client.updateMember(session, pendingAction.subject, { action });
      setFeedback({
        kind: 'success',
        message: action === 'suspend'
          ? 'Member suspended. The current API does not provide a reactivation action.'
          : 'Membership revoked. The current API does not provide a re-invitation or restore action.',
      });
      setPendingAction(null);
      setRetryCount((value) => value + 1);
    } catch (reason: unknown) {
      setFeedback({ kind: 'error', message: requestErrorMessage(reason) });
    } finally {
      setConfirming(false);
      setBusySubject(null);
    }
  }

  if (!session) {
    return (
      <StatePanel
        title="Connect your organization account"
        description="Member records are loaded only after trusted sign-in and server-side membership resolution. Authentication is not connected in this preview, so no sample users or tenant data are displayed."
      />
    );
  }

  if (session.membershipRole !== 'tenant_admin') {
    return (
      <StatePanel
        title="Tenant administrator access required"
        description="Only an active tenant administrator can list members, create invitations, change roles, suspend or revoke access. The backend independently enforces this permission."
        icon={ShieldCheck}
      />
    );
  }

  if (!hasVerifiedSubject) {
    return (
      <StatePanel
        title="Verified identity is unavailable"
        description="Member administration requires the exact subject from the trusted identity provider so the current administrator cannot manage their own membership."
        icon={AlertCircle}
      />
    );
  }

  if (clientConfig.state === 'missing') {
    return (
      <StatePanel
        title="API connection is not configured"
        description="Set VITE_AEGIS_API_BASE_URL to the HTTPS API origin. Access tokens must come from the identity provider at runtime and must never be stored in Vite environment variables."
        icon={AlertCircle}
      />
    );
  }

  if (clientConfig.state === 'invalid') {
    return (
      <StatePanel
        title="API configuration is invalid"
        description="The API origin must use HTTPS. HTTP is accepted only for localhost development, and URL credentials or path prefixes are not allowed."
        icon={AlertCircle}
      />
    );
  }

  if (loading) {
    return (
      <section aria-live="polite" className="flex min-h-[320px] items-center justify-center gap-3 text-sm text-slate-400">
        <RefreshCw size={17} className="animate-spin text-cyan-200" aria-hidden="true" />
        Loading organization members…
      </section>
    );
  }

  if (error) {
    return (
      <section role="alert" className="rounded-2xl border border-amber-200/15 bg-[#171923] p-8">
        <div className="flex items-center gap-2 text-amber-200"><AlertCircle size={17} aria-hidden="true" /><h2 className="text-sm font-semibold">Member directory unavailable</h2></div>
        <p className="mt-3 text-sm leading-6 text-slate-400">{error}</p>
        <button type="button" onClick={() => setRetryCount((value) => value + 1)} className="mt-5 inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-200 hover:bg-white/5">
          <RefreshCw size={13} aria-hidden="true" /> Retry
        </button>
      </section>
    );
  }

  if (loadedContext !== contextKey) {
    return (
      <section aria-live="polite" className="flex min-h-[320px] items-center justify-center gap-3 text-sm text-slate-400">
        <RefreshCw size={17} className="animate-spin text-cyan-200" aria-hidden="true" />
        Loading organization members…
      </section>
    );
  }

  return (
    <section aria-labelledby="membership-heading" className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">Customer administration</p>
          <h2 id="membership-heading" className="mt-2 text-2xl font-semibold text-white">Members and access</h2>
          <p className="mt-1 text-sm text-slate-500">Manage the identities that belong to this organization.</p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-2 text-[11px] text-emerald-200">
          <ShieldCheck size={13} aria-hidden="true" /> Tenant administrator
        </div>
      </div>

      <form onSubmit={(event) => void inviteMember(event)} className="rounded-2xl border border-white/[0.07] bg-[#101722] p-5 sm:p-6">
        <div className="flex items-center gap-2"><UserPlus size={17} className="text-cyan-200" aria-hidden="true" /><h3 className="text-sm font-semibold text-white">Invite an existing identity</h3></div>
        <p className="mt-2 max-w-3xl text-xs leading-5 text-slate-500">Enter the exact OIDC subject (<code>sub</code>) of a user who already exists in your identity provider. This creates a pending grant that expires after seven days; it does not send email or create an identity-provider account.</p>
        <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_220px_auto] md:items-end">
          <label className="text-xs text-slate-500">Identity subject
            <input
              required
              maxLength={128}
              value={inviteSubject}
              onChange={(event) => setInviteSubject(event.target.value)}
              placeholder="issuer|existing-user-id"
              autoComplete="off"
              className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-200/40"
            />
          </label>
          <label className="text-xs text-slate-500">Initial role
            <select
              value={inviteRole}
              onChange={(event) => setInviteRole(event.target.value as AssignableMemberRole)}
              className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white"
            >
              {ASSIGNABLE_MEMBER_ROLES.map((role) => <option key={role} value={role}>{humanize(role)}</option>)}
            </select>
          </label>
          <button type="submit" disabled={savingInvite || inviteSubject.trim().length === 0} className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-300 px-4 py-2.5 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">
            <UserPlus size={14} aria-hidden="true" /> {savingInvite ? 'Creating…' : 'Create invitation'}
          </button>
        </div>
      </form>

      {feedback && (
        <div role={feedback.kind === 'error' ? 'alert' : 'status'} className={feedback.kind === 'error' ? 'rounded-xl border border-rose-300/20 bg-rose-300/[0.06] p-4 text-xs text-rose-200' : 'rounded-xl border border-emerald-300/20 bg-emerald-300/[0.06] p-4 text-xs text-emerald-200'}>
          {feedback.message}
        </div>
      )}

      {pendingAction && pendingAction.contextKey === contextKey && (
        <section aria-labelledby="confirm-member-action" className="rounded-xl border border-amber-300/20 bg-amber-300/[0.06] p-4">
          <h3 id="confirm-member-action" className="text-sm font-semibold text-amber-100">
            Confirm {pendingAction.action} for {pendingAction.subject}
          </h3>
          <p className="mt-2 text-xs leading-5 text-amber-100/70">
            {pendingAction.action === 'suspend'
              ? 'This blocks the member from accessing the organization. The current API has no reactivation action.'
              : 'This permanently revokes the membership in the current API. A revoked subject cannot be re-invited through the existing lifecycle endpoint.'}
          </p>
          <div className="mt-4 flex gap-2">
            <button type="button" disabled={confirming} onClick={() => setPendingAction(null)} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 disabled:opacity-50">Cancel</button>
            <button type="button" disabled={confirming} onClick={() => void confirmMemberAction()} className="rounded-lg bg-amber-300 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">
              {confirming ? 'Applying…' : 'Confirm action'}
            </button>
          </div>
        </section>
      )}

      <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-[#101722]">
        <div className="flex flex-col justify-between gap-2 border-b border-white/[0.06] px-5 py-4 sm:flex-row sm:items-center">
          <div><h3 className="text-sm font-semibold text-white">Organization members</h3><p className="mt-1 text-[11px] text-slate-500">{members.length} membership records</p></div>
          <button type="button" onClick={() => setRetryCount((value) => value + 1)} disabled={loading} className="inline-flex items-center gap-2 self-start rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-slate-300 disabled:opacity-50">
            <RefreshCw size={13} aria-hidden="true" /> Refresh
          </button>
        </div>

        {members.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Users size={24} className="mx-auto text-slate-600" aria-hidden="true" />
            <h4 className="mt-3 text-sm font-medium text-slate-300">No membership records returned</h4>
            <p className="mt-1 text-xs text-slate-500">The organization member list is empty.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-left text-xs">
              <caption className="sr-only">Organization membership directory</caption>
              <thead className="bg-[#0d141e] text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium">Identity subject</th>
                  <th scope="col" className="px-4 py-3 font-medium">Role</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 font-medium">Created / expires</th>
                  <th scope="col" className="px-4 py-3 font-medium">Access controls</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {members.map((member) => {
                  const isSelf = member.subject === session.subject;
                  const selectedRole = selectedRoles[member.id] ?? member.role;
                  const roleChanged = selectedRole !== member.role && isAssignableRole(selectedRole);
                  const isBusy = busySubject === member.subject;

                  return (
                    <tr key={member.id} className="align-top text-slate-300">
                      <td className="px-5 py-4">
                        <p className="break-all font-medium text-white">{member.subject}</p>
                        {isSelf && <span className="mt-1 inline-flex items-center gap-1 text-[10px] text-cyan-200"><Check size={11} aria-hidden="true" /> You</span>}
                      </td>
                      <td className="px-4 py-4">
                        <label className="sr-only" htmlFor={'role-' + member.id}>Role for {member.subject}</label>
                        <select
                          id={'role-' + member.id}
                          value={selectedRole}
                          disabled={isSelf || member.status === 'revoked' || isBusy}
                          onChange={(event) => setSelectedRoles((current) => ({ ...current, [member.id]: event.target.value as MemberRole }))}
                          className="rounded-lg border border-white/[0.09] bg-[#0b1018] px-2.5 py-2 text-xs text-white disabled:opacity-60"
                        >
                          {member.role === 'tenant_admin' && <option value="tenant_admin" disabled>Tenant administrator</option>}
                          {ASSIGNABLE_MEMBER_ROLES.map((role) => <option key={role} value={role}>{humanize(role)}</option>)}
                        </select>
                        {roleChanged && !isSelf && (
                          <button type="button" disabled={isBusy} onClick={() => void changeMemberRole(member)} className="mt-2 block rounded-lg border border-cyan-200/20 px-2.5 py-1.5 text-[10px] text-cyan-100 disabled:opacity-50">
                            Save role
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-4"><MemberStatusLabel status={member.status} /></td>
                      <td className="px-4 py-4">
                        <p>{dateLabel(member.created_at)}</p>
                        {member.status === 'pending' && member.invitation_expires_at && (
                          <p className="mt-1 inline-flex items-center gap-1 text-[10px] text-amber-200"><Clock3 size={11} aria-hidden="true" /> Expires {dateLabel(member.invitation_expires_at)}</p>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {isSelf ? (
                          <span className="text-[10px] text-slate-500">Self-management disabled</span>
                        ) : member.status === 'revoked' ? (
                          <span className="text-[10px] text-slate-500">No further actions</span>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {member.status === 'active' && (
                              <button type="button" disabled={isBusy} onClick={() => setPendingAction({ subject: member.subject, action: 'suspend', contextKey: contextKey ?? '' })} className="rounded-lg border border-amber-300/20 px-2.5 py-1.5 text-[10px] text-amber-200 disabled:opacity-50">
                                Suspend
                              </button>
                            )}
                            <button type="button" disabled={isBusy} onClick={() => setPendingAction({ subject: member.subject, action: 'revoke', contextKey: contextKey ?? '' })} className="inline-flex items-center gap-1 rounded-lg border border-rose-300/20 px-2.5 py-1.5 text-[10px] text-rose-200 disabled:opacity-50">
                              <UserRoundX size={11} aria-hidden="true" /> Revoke
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-white/[0.07] bg-[#0e141e] p-4">
        <ShieldCheck size={16} className="mt-0.5 text-slate-400" aria-hidden="true" />
        <p className="text-xs leading-5 text-slate-500">
          The backend rechecks tenant-admin authority and protects the last active administrator. Invitations target existing OIDC subjects and do not send email. Suspended memberships cannot currently be reactivated, and revoked memberships cannot currently be restored or re-invited through this API.
        </p>
      </div>
    </section>
  );
}
