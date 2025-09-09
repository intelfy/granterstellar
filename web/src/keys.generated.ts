/** AUTO-GENERATED: DO NOT EDIT. Source: locales/en.yml */
export const KEYS = {
  'ai.revise.locked': "Section is locked. Unlock before revising.",
  'billing.checkout.success_title': "Subscription active",
  'errors.generic.unexpected': "Something went wrong. Please try again.",
  'errors.revision.cap_reached': "You've reached the revision limit ({count}/{limit}).",
  'ui.nav.dashboard': "Dashboard",
  'ui.proposals.empty_state': "No proposals yet",
} as const;

export type Key = keyof typeof KEYS;

export function t(key: Key, params?: Record<string, string | number>): string {
  let msg = KEYS[key];
  if (!params) return msg;
  return msg.replace(/\{(\w+)\}/g, (_, p) => (p in params ? String(params[p]) : '{' + p + '}'));
}
