import browser from "webextension-polyfill"
import { Prompt } from "./prompt-repository"
import { AuthService, AuthConfig } from "./auth"
import { fetchJson, fetchStreamJson } from "./http"
import { AgentFlow } from "./flow"

// Type definition for token response from the backend
export interface TokenResponse {
  type: "tokens"
  tokens: number
  thoughts_tokens?: number
}

// Type definition for thinking mode response chunks
export interface ThinkingChunk {
  type: "content" | "thought" | "tokens" | "end" | "error"
  content?: string
  tokens?: number
  thoughts_tokens?: number
  error?: string
}

export class Agent {
    url: string
    logo: string
    manifest: AgentManifest
    activationRule?: AgentRule
    activationAction?: ActivationAction

    private constructor(url: string, manifest: AgentManifest) {
        this.url = url
        this.logo = `${url}/logo.png`
        this.manifest = manifest
        this.activationRule = manifest.onHttpRequest?.find(r => r.actions.find(a => a.activate))
        this.activationAction = this.activationRule?.actions.find(a => a.activate)?.activate
    }

    public static async fromUrl(url: string): Promise<Agent> {
        url = url.endsWith("/") ? url.slice(0, -1) : url
        const manifestPath = "/manifest.json"
        url = url.endsWith(manifestPath) ? url.slice(0, -manifestPath.length) : url
        return new Agent(url, await fetchJson(`${url}/manifest.json`))
    }

    public static fromJsonObject(obj: any): Agent {
        return new Agent(obj.url, obj.manifest)
    }

    public async createSession(locales: string[], authService?: AuthService): Promise<AgentSession> {
        if (authService) {
            await authService.login()
        }
        return await this.postJson(`${this.url}/sessions`, { locales: locales }, authService)
    }

    private async postJson(url: string, body: any, authService?: AuthService): Promise<any> {
        return await fetchJson(url, await this.buildHttpPost(body, authService))
    }

    private async buildHttpPost(body: any, authService?: AuthService): Promise<RequestInit> {
        const headers = { "Content-Type": "application/json" } as any
        if (authService) {
            const user = await authService.getUser()
            headers['Authorization'] = "Bearer " + user!.access_token
        }
        return {
            method: "POST",
            headers: headers,
            body: JSON.stringify(body)
        }
    }

    public activatesOn(req: RequestEvent): boolean {
        if (!this.activationRule) {
            return false
        }
        return this.requestMatchesRuleCondition(req, this.activationRule)
    }

    private requestMatchesRuleCondition(req: RequestEvent, rule: AgentRule): boolean {
        return new RegExp(rule.condition.urlRegex!).test(req.details.url)
            && (!rule.condition.requestMethods || rule.condition.requestMethods!.includes(req.details.method.toLowerCase()))
            && (!rule.condition.resourceTypes || rule.condition.resourceTypes!.includes(req.details.type))
            && (!rule.condition.event && req.event === RequestEventType.OnCompleted || rule.condition.event === req.event)
    }

    public findMatchingActions(req: RequestEvent): AgentRuleAction[] {
        return this.manifest.onHttpRequest ? this.manifest.onHttpRequest.filter(r => this.requestMatchesRuleCondition(req, r))
            .flatMap(r => r.actions) : []
    }

    /**
     * Common streaming method that handles the shared logic for all endpoint types
     */
    private async * streamFromEndpoint<T>(
        endpoint: string,
        msg: string,
        authService?: AuthService,
        abortSignal?: AbortSignal,
        chunkProcessor?: (part: any) => T | string | null
    ): AsyncIterable<T | string | AgentFlow> {
        const options = await this.buildHttpPost({ question: msg }, authService)
        
        if (abortSignal) {
            options.signal = abortSignal
        }
        
        const ret = await fetchStreamJson(`${this.sessionUrl("")}${endpoint}`, options)
        
        for await (const part of ret) {
            if (abortSignal?.aborted) {
                console.log(`Agent.${endpoint}: Stream cancelled by AbortSignal`);
                break;
            }
            
            if (typeof part === "string") {
                yield part;
            } else if (part && typeof part === "object" && part.type) {
                // Use custom processor if provided, otherwise use default logic
                if (chunkProcessor) {
                    const processed = chunkProcessor(part);
                    if (processed !== null) {
                        yield processed as T | string;
                    }
                } else {
                    // Default processing for content and errors
                    if (part.type === "content" && part.content) {
                        yield part.content;
                    } else if (part.type === "error") {
                        throw new Error(part.error || "Unknown error occurred");
                    } else if (part.type === "end") {
                        break;
                    }
                }
            } else {
                try {
                    yield AgentFlow.fromJsonObject(part);
                } catch (e) {
                    console.warn(`Received invalid object from ${endpoint} stream, skipping:`, part, e);
                }
            }
        }
    }

    public async * ask(msg: string, sessionId: string, authService?: AuthService, abortSignal?: AbortSignal): AsyncIterable<string | TokenResponse | AgentFlow> {
        const chunkProcessor = (part: any): TokenResponse | string | null => {
            if (part.type === "content" && part.content) {
                return part.content;
            } else if (part.type === "tokens") {
                return part as TokenResponse;
            } else if (part.type === "error") {
                throw new Error(part.error || "Unknown error occurred");
            } else if (part.type === "end") {
                return null; // Signal to break
            }
            return null;
        };

        yield* this.streamFromEndpoint(`/sessions/${sessionId}/questions`, msg, authService, abortSignal, chunkProcessor);
    }

    public async * chat(msg: string, sessionId: string, authService?: AuthService, abortSignal?: AbortSignal): AsyncIterable<string | TokenResponse | AgentFlow> {
        const chunkProcessor = (part: any): TokenResponse | string | null => {
            if (part.type === "content" && part.content) {
                return part.content;
            } else if (part.type === "tokens") {
                return part as TokenResponse;
            } else if (part.type === "error") {
                throw new Error(part.error || "Unknown error occurred");
            } else if (part.type === "end") {
                return null; // Signal to break
            }
            return null;
        };

        yield* this.streamFromEndpoint(`/sessions/${sessionId}/chat-gemini`, msg, authService, abortSignal, chunkProcessor);
    }

    public async * chatThinking(msg: string, sessionId: string, authService?: AuthService, abortSignal?: AbortSignal): AsyncIterable<string | ThinkingChunk | AgentFlow> {
        const chunkProcessor = (part: any): ThinkingChunk | string | null => {
            if (part.type === "content" && part.content) {
                return part.content;
            } else if (part.type === "thought" && part.content) {
                return part as ThinkingChunk;
            } else if (part.type === "tokens") {
                return part as ThinkingChunk;
            } else if (part.type === "error") {
                throw new Error(part.error || "Unknown error occurred");
            } else if (part.type === "end") {
                return null; // Signal to break
            }
            return null;
        };

        yield* this.streamFromEndpoint(`/sessions/${sessionId}/thinking-chat-gemini`, msg, authService, abortSignal, chunkProcessor);
    }

    private sessionUrl(sessionId: string): string {
        return `${this.url}/sessions/${sessionId}`
    }

    public async transcriptAudio(audioFileBase64: string, sessionId: string, authService?: AuthService) {
        const ret = await this.postJson(`${this.sessionUrl(sessionId)}/transcriptions`, { file: audioFileBase64 }, authService)
        return ret.text
    }

    public async solveInteractionSummary(detail: any, sessionId: string, authService?: AuthService): Promise<string> {
        const ret = await this.postJson(`${this.sessionUrl(sessionId)}/interactions`, detail, authService)
        return ret.summary
    }

}

export interface AgentManifest {
    id: string
    name: string
    capabilities?: string[]
    welcomeMessage: string
    prompts?: Prompt[]
    onSessionClose?: EndAction
    onHttpRequest?: AgentRule[]
    pollInteractionPeriodSeconds?: number
    auth?: AuthConfig
    contactEmail: string
}

export interface AgentRule {
    condition: AgentRuleCondition
    actions: AgentRuleAction[]
}

export interface AgentRuleCondition {
    urlRegex: string
    requestMethods?: string[]
    resourceTypes?: string[]
    event?: string
}

export interface AgentRuleAction {
    activate?: ActivationAction
    addHeader?: AddHeaderRuleAction
    recordInteraction?: RecordInteractionRuleAction
}

export interface ActivationAction {
    httpRequest?: HttpRequestAction
}

export interface EndAction {
    httpRequest: HttpRequestAction
}

export interface HttpRequestAction {
    url: string
    method?: string
}

export interface AddHeaderRuleAction {
    header: string
    value: string
}

export interface RecordInteractionRuleAction {
    httpRequest?: HttpRequestAction
}

export interface AgentSession {
    id: string
}

export class RequestEvent {
    event: RequestEventType;
    details: browser.WebRequest.OnCompletedDetailsType | browser.WebRequest.OnBeforeRequestDetailsType;

    constructor(event: RequestEventType, details: browser.WebRequest.OnCompletedDetailsType | browser.WebRequest.OnBeforeRequestDetailsType) {
        this.event = event;
        this.details = details;
    }
}

export enum RequestEventType {
    OnBeforeRequest = "onBeforeRequest",
    OnCompleted = "onCompleted",
}
