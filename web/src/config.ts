export const flags = {
  // Vite injects import.meta.env; add a ts-ignore for editors without vite/client types.
  // @ts-ignore
  UI_EXPERIMENTS: Boolean(import.meta.env && (import.meta as any).env && (import.meta as any).env.VITE_UI_EXPERIMENTS),
} as const;

export type Flags = typeof flags;
