import { vi } from 'vitest'

// Mock webextension-polyfill before it loads
vi.mock('webextension-polyfill', () => ({
  default: {
    storage: {
      local: {
        get: vi.fn(),
        set: vi.fn(),
      },
    },
    runtime: {
      onMessage: {
        addListener: vi.fn(),
        removeListener: vi.fn(),
      },
    },
  },
}))

// Mock global browser object
global.browser = {
  storage: {
    local: {
      get: vi.fn(),
      set: vi.fn(),
    },
  },
  runtime: {
    onMessage: {
      addListener: vi.fn(),
      removeListener: vi.fn(),
    },
  },
}

// Mock fetch for HTTP requests
global.fetch = vi.fn()

// Mock AbortController
global.AbortController = class AbortController {
  signal = { aborted: false }
  abort() {
    this.signal.aborted = true
  }
}

// Mock console methods to avoid noise in tests
global.console = {
  ...global.console,
  warn: vi.fn(),
  error: vi.fn(),
  log: vi.fn(),
}

// Mock TextEncoder/TextDecoder
global.TextEncoder = class TextEncoder {
  encode(str: string) {
    return new Uint8Array(Buffer.from(str))
  }
}

global.TextDecoder = class TextDecoder {
  decode(bytes: Uint8Array) {
    return Buffer.from(bytes).toString()
  }
}