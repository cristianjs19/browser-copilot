export const fetchJson = async (url: string, options?: RequestInit) => {
  let ret = await fetchResponse(url, options)
  return await ret.json()
}

const fetchResponse = async (url: string, options?: RequestInit) => {
  let ret = await fetch(url, options)
  if (ret.status < 200 || ret.status >= 300) {
    let body = await ret.text()
    console.warn(`Problem with ${options?.method ? options.method : 'GET'} ${url}`, { status: ret.status, body: body })
    if (ret.headers.get('Content-Type') === 'application/json') {
      let json = JSON.parse(body)
      if ('detail' in json) {
        throw new HttpServiceError(json.detail)
      }
    }
    throw new HttpServiceError()
  }
  return ret
}

export class HttpServiceError extends Error {
  detail?: string

  constructor(detail?: string) {
    super()
    this.detail = detail
  }

}

export async function* fetchStreamJson(url: string, options?: RequestInit): AsyncIterable<any> {
  let resp = await fetchResponse(url, options)
  let contentType = resp.headers.get("content-type")
  if (contentType?.startsWith("text/event-stream")) {
    let ret = await fetchSSEStream(resp, url, options)
    for await (const part of ret) {
      yield part
    }
  } else {
    yield resp.json()
  }
}

async function* fetchSSEStream(resp: Response, url: string, options?: RequestInit): AsyncIterable<any> {
  let reader = resp.body!.getReader()
  let done = false
  let buffer = ''
  
  while (!done) {
    let result = await reader.read()
    done = result.done
    
    if (result.value) {
      // Accumulate the new data in the buffer
      buffer += new TextDecoder("utf-8").decode(result.value)
      
      // Process complete events from the buffer
      let eventEnd = buffer.indexOf('\n\n')
      while (eventEnd !== -1) {
        let eventData = buffer.substring(0, eventEnd)
        buffer = buffer.substring(eventEnd + 2)
        
        if (eventData.trim()) {
          try {
            const event = ServerSentEvent.parseEventString(eventData)
            if (event.event === "error") {
              console.warn(`Problem while reading stream response from ${options?.method ? options.method : 'GET'} ${url}`, event)
              throw new HttpServiceError()
            }
            
            if (event.event) {
              yield JSON.parse(event.data)
            } else {
              // Parse JSON data for StreamingChunk format
              try {
                const parsed = JSON.parse(event.data)
                yield parsed
              } catch (e) {
                // Log the parsing error and skip malformed chunks instead of yielding raw data
                console.warn(`Failed to parse SSE chunk as JSON, skipping: ${event.data}`, e)
                // Don't yield anything for malformed chunks - just skip them
              }
            }
          } catch (e) {
            console.warn(`Failed to parse SSE event, skipping: ${eventData}`, e)
          }
        }
        
        eventEnd = buffer.indexOf('\n\n')
      }
    }
  }
  
  // Process any remaining data in the buffer
  if (buffer.trim()) {
    try {
      const event = ServerSentEvent.parseEventString(buffer)
      if (event.data.trim()) {
        try {
          const parsed = JSON.parse(event.data)
          yield parsed
        } catch (e) {
          console.warn(`Failed to parse final SSE chunk as JSON, skipping: ${event.data}`, e)
        }
      }
    } catch (e) {
      console.warn(`Failed to parse final SSE event, skipping: ${buffer}`, e)
    }
  }
}

class ServerSentEvent {
  event?: string
  data: string

  constructor(data: string, event?: string) {
    this.data = data
    this.event = event
  }

  public static fromBytes(bs: Uint8Array): ServerSentEvent[] {
    let text = new TextDecoder("utf-8").decode(bs)
    let events = text.split(/\r\n\r\n/)
    return events
      .map(e => ServerSentEvent.parseEvent(e))
      .filter(event => event.data.trim() !== '') // Filter out empty events
  }

  private static parseEvent(event: string): ServerSentEvent {
    let parts = event.split(/\r\n/)
    let eventType
    let eventPrefix = "event: "
    if (parts[0].startsWith(eventPrefix)) {
      eventType = parts[0].substring(eventPrefix.length)
    }
    let dataPrefix = "data: "
    let data = parts.filter(p => p.startsWith(dataPrefix)).map(p => p.substring(dataPrefix.length)).join("\n")
    return new ServerSentEvent(data, eventType)
  }

  public static parseEventString(event: string): ServerSentEvent {
    let parts = event.split(/\r?\n/)
    let eventType: string | undefined
    let data: string = ''
    
    for (const part of parts) {
      if (part.startsWith('event: ')) {
        eventType = part.substring('event: '.length)
      } else if (part.startsWith('data: ')) {
        data = part.substring('data: '.length)
      }
    }
    
    return new ServerSentEvent(data, eventType)
  }
}
