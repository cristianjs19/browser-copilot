import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchStreamJson } from '../src/scripts/http'

describe('HTTP Streaming', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchStreamJson', () => {
    it('should handle server-sent events streaming', async () => {
      const mockResponse = {
        status: 200,
        headers: new Map([['content-type', 'text/event-stream']]),
        body: {
          getReader: () => ({
            read: vi.fn()
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: {"type":"content","content":"Hello "}\n\n')
              })
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: {"type":"content","content":"World!"}\n\n')
              })
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: {"type":"tokens","tokens":10}\n\n')
              })
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: {"type":"end"}\n\n')
              })
              .mockResolvedValueOnce({ done: true }),
            cancel: vi.fn()
          })
        }
      }

      global.fetch = vi.fn().mockResolvedValue(mockResponse)

      const results = []
      for await (const chunk of fetchStreamJson('http://test.com/stream')) {
        results.push(chunk)
      }

      expect(results).toEqual([
        { type: 'content', content: 'Hello ' },
        { type: 'content', content: 'World!' },
        { type: 'tokens', tokens: 10 },
        { type: 'end' }
      ])
    })

    it('should handle regular JSON responses', async () => {
      const mockResponse = {
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: () => Promise.resolve({ message: 'Hello World' })
      }

      global.fetch = vi.fn().mockResolvedValue(mockResponse)

      const results = []
      for await (const chunk of fetchStreamJson('http://test.com/api')) {
        results.push(chunk)
      }

      expect(results).toEqual([{ message: 'Hello World' }])
    })

    it('should handle malformed SSE chunks gracefully', async () => {
      const mockResponse = {
        status: 200,
        headers: new Map([['content-type', 'text/event-stream']]),
        body: {
          getReader: () => ({
            read: vi.fn()
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: {"type":"content","content":"Valid"}\n\n')
              })
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: invalid json\n\n')
              })
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: {"type":"end"}\n\n')
              })
              .mockResolvedValueOnce({ done: true }),
            cancel: vi.fn()
          })
        }
      }

      global.fetch = vi.fn().mockResolvedValue(mockResponse)

      const results = []
      for await (const chunk of fetchStreamJson('http://test.com/stream')) {
        results.push(chunk)
      }

      // Should skip malformed chunks and continue
      expect(results).toEqual([
        { type: 'content', content: 'Valid' },
        { type: 'end' }
      ])
    })

    it('should handle abort signal', async () => {
      const abortController = new AbortController()
      
      const mockResponse = {
        status: 200,
        headers: new Map([['content-type', 'text/event-stream']]),
        body: {
          getReader: () => ({
            read: vi.fn()
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode('data: {"type":"content","content":"Start"}\n\n')
              })
              .mockImplementation(() => {
                abortController.abort()
                return Promise.resolve({ done: true })
              }),
            cancel: vi.fn()
          })
        }
      }

      global.fetch = vi.fn().mockResolvedValue(mockResponse)

      const results = []
      for await (const chunk of fetchStreamJson('http://test.com/stream', { signal: abortController.signal })) {
        results.push(chunk)
      }

      expect(results).toEqual([{ type: 'content', content: 'Start' }])
    })
  })
})