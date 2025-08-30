import '@testing-library/jest-dom/vitest'
import { beforeAll, vi } from 'vitest'

// Silence jsdom "Not implemented: window.alert/confirm" warnings in tests
// and provide stable defaults for confirm flows in UI components.
// These can be overridden per-test if needed.
beforeAll(() => {
	if (typeof window !== 'undefined') {
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		;(window as any).alert = vi.fn()
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		;(window as any).confirm = vi.fn(() => true)
	} else {
		// Fallback in case environment isn't jsdom for a specific test
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		;(globalThis as any).alert = vi.fn()
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		;(globalThis as any).confirm = vi.fn(() => true)
	}
})
