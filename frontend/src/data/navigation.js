// @ts-check

/**
 * @typedef {{ id: 'overview' | 'investigations' | 'agents' | 'integrations' | 'memory' | 'audit', label: string, description: string }} NavigationItem
 */

/** @type {readonly NavigationItem[]} */
export const navigationItems = Object.freeze([
  {
    id: 'overview',
    label: 'Overview',
    description: 'A clear view of your defensive security workspace.',
  },
  {
    id: 'investigations',
    label: 'Investigations',
    description: 'Review scoped cases, evidence, and analyst decisions.',
  },
  {
    id: 'agents',
    label: 'AI agents',
    description: 'Manage narrowly scoped assistants and their permissions.',
  },
  {
    id: 'integrations',
    label: 'Integrations',
    description: 'Connect approved telemetry and defensive security tools.',
  },
  {
    id: 'memory',
    label: 'Memory',
    description: 'Inspect retained context, access rules, and retention.',
  },
  {
    id: 'audit',
    label: 'Audit log',
    description: 'Trace system activity and human approvals.',
  },
]);
