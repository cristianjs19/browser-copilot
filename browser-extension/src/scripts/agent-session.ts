import browser from "webextension-polyfill"
import { Agent, AgentRuleCondition, AddHeaderRuleAction, RecordInteractionRuleAction, RequestEvent, TokenResponse, ThinkingChunk } from "./agent"
import { AgentFlow } from "./flow"
import { AuthService } from "./auth"
import { HttpServiceError, fetchJson } from "./http"
import { BrowserMessage, InteractionSummary } from "./browser-message"
import { FlowExecutor } from "./flow"
import { getUserThinkingModePreference } from "./agent-repository"

// Global streaming controller registry to handle the serialization issue
class StreamingControllerRegistry {
  private static controllers: Map<string, AbortController> = new Map()
  
  static setController(sessionId: string, controller: AbortController) {
    this.controllers.set(sessionId, controller)
  }
  
  static getController(sessionId: string): AbortController | undefined {
    const controller = this.controllers.get(sessionId)
    return controller
  }
  
  static removeController(sessionId: string) {
    this.controllers.delete(sessionId)
  }
  
  static abortStreaming(sessionId: string): boolean {
    const controller = this.controllers.get(sessionId)
    if (controller) {
      console.log(`StreamingRegistry: Aborting streaming for session ${sessionId}`);
      controller.abort()
      this.controllers.delete(sessionId)
      return true
    }
    console.log(`StreamingRegistry: No controller found for session ${sessionId}`);
    return false
  }
}

export class AgentSession {
  tabId: number
  agent: Agent
  url: string
  id?: string
  authService?: AuthService
  pollId?: number

  constructor(tabId: number, agent: Agent, url: string, id?: string, pollId?: number) {
    this.id = id
    this.tabId = tabId
    this.agent = agent
    this.url = url
    this.authService = this.agent.manifest.auth ? new AuthService(this.agent.manifest.auth) : undefined
    this.pollId = pollId
  }

  public static fromJsonObject(obj: any): AgentSession {
    return new AgentSession(obj.tabId, Agent.fromJsonObject(obj.agent), obj.url, obj.id, obj.pollId)
  }

  // cannot just import sendToTab from background.ts as it will re register listeners and cause requests to be processed twice and message duplication in ui
  public async activate(msgSender: (msg: BrowserMessage) => void) {
    let resp = await this.agent.createSession(await browser.i18n.getAcceptLanguages(), this.authService)
    this.id = resp.id
    let httpAction = this.agent.activationAction?.httpRequest
    if (httpAction) {
      await fetchJson(this.solveUrlTemplate(httpAction.url, this.url), { method: httpAction.method })
    }
    await this.updateRequestRules()
    await this.startPolling(msgSender)
  }

  private solveUrlTemplate(urlTemplate: string, baseUrl: string): string {
    let parsedUrl = new URL(baseUrl)
    let basePath = parsedUrl.pathname.substring(1, parsedUrl.pathname.lastIndexOf("/"))
    let ret = urlTemplate.replace("${origin}", parsedUrl.origin).replace("${basePath}", basePath).replace("${sessionId}", this.id!)
    return ret
  }

  private async updateRequestRules() {
    if (!this.agent.manifest.onHttpRequest) {
      return
    }
    let lastRuleId = await this.getLastRuleId()
    let requestRules = this.agent.manifest.onHttpRequest
      .flatMap(r => r.actions
        .filter(a => a.addHeader)
        .map(a => this.buildModifyHeadersRule(lastRuleId++, r.condition, a.addHeader!))
      )
    if (!requestRules) {
      return
    }
    let prevRuleIds = await this.getTabPreviousRuleIds()
    await browser.declarativeNetRequest.updateSessionRules({
      removeRuleIds: prevRuleIds,
      addRules: requestRules
    })
  }

  private async getLastRuleId(): Promise<number> {
    let rules = await browser.declarativeNetRequest.getSessionRules()
    return Math.max(...rules.map(r => r.id))
  }

  private buildModifyHeadersRule(ruleId: number, condition: AgentRuleCondition, action: AddHeaderRuleAction): browser.DeclarativeNetRequest.Rule {
    return {
      id: ruleId,
      priority: 1,
      action: {
        type: "modifyHeaders",
        requestHeaders: [{
          operation: "set",
          header: action.header,
          value: action.value.replace("${sessionId}", this.id!)
        }]
      },
      condition: {
        tabIds: [this.tabId],
        regexFilter: condition.urlRegex,
        requestMethods: condition.requestMethods,
        resourceTypes: condition.resourceTypes as browser.DeclarativeNetRequest.ResourceType[]
      }
    }
  }

  private async getTabPreviousRuleIds(): Promise<number[]> {
    const prevRules = await browser.declarativeNetRequest.getSessionRules()
    return prevRules.filter(r => r.condition.tabIds?.includes(this.tabId)).map(r => r.id)
  }

  private async startPolling(msgSender: (msg: BrowserMessage) => void) {
    const pollPeriodSeconds = this.agent.manifest.pollInteractionPeriodSeconds
    if (pollPeriodSeconds) {
      this.pollId = setInterval(async () => await this.pollInteraction(msgSender), pollPeriodSeconds * 1000)
    }
  }

  private async pollInteraction(msgSender: (msg: BrowserMessage) => void) {
    try {
      const summary = await this.agent.solveInteractionSummary(undefined, this.id!, this.authService)
      if (summary) {
        await msgSender(new InteractionSummary(true, summary))
      }
    } catch (e) {
      // exceptions from http methods are already logged so no need to handle them
      msgSender(new InteractionSummary(false, e instanceof HttpServiceError ? e.detail : undefined));
    }
  }

  public async processInteraction(req: RequestEvent): Promise<string | undefined> {
    const actions = this.agent.findMatchingActions(req)
    for (const a of actions) {
      if (a.recordInteraction) {
        const interactionDetail = await this.findInteraction(req, a.recordInteraction)
        return await this.agent.solveInteractionSummary(interactionDetail, this.id!, this.authService)
      }
    }
  }

  private async findInteraction(req: RequestEvent, action: RecordInteractionRuleAction): Promise<any> {
    if (action.httpRequest) {
      return await fetchJson(this.solveUrlTemplate(action.httpRequest.url, req.details.url), { method: action.httpRequest.method })
    } else {
      const body = (req.details as browser.WebRequest.OnBeforeRequestDetailsType).requestBody?.raw
      if (!body || !body[0].bytes) {
        return null
      }
      return JSON.parse(new TextDecoder("utf-8").decode(body[0].bytes))
    }
  }

  public async processUserMessage(text: string, file: Record<string, string>, msgHandler: (text: string, complete: boolean, tokens?: number, thoughtsTokens?: number, thoughts?: string) => void, errorHandler: (error: any) => void) {
    
    if (!this.id) {
      console.error("AgentSession: No session ID available");
      errorHandler(new Error("No session ID available"));
      return;
    }
    
    // Cancel any existing streaming for this session
    StreamingControllerRegistry.abortStreaming(this.id);
    
    // Create new controller for this streaming operation
    const streamingController = new AbortController()
    const signal = streamingController.signal
    
    // Store the controller in the registry
    StreamingControllerRegistry.setController(this.id, streamingController);
    
    try {
      if (file.data) {
        text = await this.agent.transcriptAudio(file.data, this.id, this.authService);
      }
      
      // Check if agent has thinking mode capability
      const hasThinkingMode = this.agent.manifest.capabilities?.includes('has_thinking_mode') || false;
      
      let ret: AsyncIterable<string | TokenResponse | ThinkingChunk | AgentFlow>;
      
      if (hasThinkingMode) {
        // Check if thinking mode is enabled for this agent
        const thinkingModeEnabled = await getUserThinkingModePreference(this.agent.manifest.id);
        
        // Use appropriate chat method based on thinking mode
        ret = thinkingModeEnabled 
          ? this.agent.chatThinking(text, this.id, this.authService, signal)
          : this.agent.chat(text, this.id, this.authService, signal);
      } else {
        // Use the ask method for agents without thinking mode capability
        ret = this.agent.ask(text, this.id, this.authService, signal);
      }
      
      let tokens: number | undefined;
      let thoughtsTokens: number | undefined;
      let hasTokens = false;
      let streamingStopped = false;
      let thoughts = "";
      
      for await (const part of ret) {
        if (signal.aborted) {
          streamingStopped = true;
          break;
        }
        
        if (typeof part === "string") {
          msgHandler(part, false)
        } else if (this.isTokenResponse(part)) {
          tokens = part.tokens;
          thoughtsTokens = part.thoughts_tokens;
          hasTokens = true;
        } else if (this.isThinkingChunk(part)) {
          if (part.type === "thought" && part.content) {
            thoughts += part.content;
            msgHandler("", false, undefined, undefined, thoughts);
          } else if (part.type === "tokens") {
            tokens = part.tokens;
            thoughtsTokens = part.thoughts_tokens;
            hasTokens = true;
          }
        } else {
          await new FlowExecutor(this.tabId, msgHandler).runFlow(part.steps)
        }
      }
      
      if (streamingStopped) {
        console.log("AgentSession: Stream was stopped by user");
        msgHandler("", true);
        return;
      }
      
      // Send final message with token information
      if (hasTokens) {
        msgHandler("", true, tokens, thoughtsTokens, thoughts || undefined)
      } else {
        msgHandler("", true, undefined, undefined, thoughts || undefined)
      }
    } catch (e) {
      console.log("AgentSession: Error in processUserMessage:", e);
      if (signal.aborted) {
        console.log("AgentSession: Error was due to abort signal");
        msgHandler("", true);
      } else {
        errorHandler(e)
      }
    } finally {;
      // Clean up the controller from registry
      if (this.id) {
        StreamingControllerRegistry.removeController(this.id);
      }
    }
  }

  private isTokenResponse(obj: any): obj is TokenResponse {
    return typeof obj === "object" && obj.type === "tokens";
  }

  private isThinkingChunk(obj: any): obj is ThinkingChunk {
    return typeof obj === "object" && obj.type && ["thought", "tokens"].includes(obj.type);
  }

  public async resumeFlow(msgHandler: (text: string, complete: boolean, tokens?: number, thoughtsTokens?: number) => void, errorHandler: (error: any) => void) {
    try {
      await new FlowExecutor(this.tabId, msgHandler).resumeFlow()
    } catch (e) {
      errorHandler(e)
    }
  }

  public async close() {
    await this.removeRequestRules()
    await this.stopPolling()
    
    // Clean up any streaming controllers
    if (this.id) {
      StreamingControllerRegistry.abortStreaming(this.id);
    }
    
    try {
      const endAction = this.agent.manifest.onSessionClose
      if (endAction) {
        await fetchJson(this.solveUrlTemplate(endAction.httpRequest.url, this.url), { method: endAction.httpRequest.method })
      }
    } catch (e) {
      // here we can't provide a toast as we do in activation since tab is closed and there is no content where toast can be shown
      console.error(`Problem closing session. Please contact support at ${this.agent.manifest.contactEmail} with the details.`, e)
    }
  }

  private async removeRequestRules() {
    const prevRuleIds = await this.getTabPreviousRuleIds()
    await browser.declarativeNetRequest.updateSessionRules({ removeRuleIds: prevRuleIds })
  }

  private async stopPolling() {
    if (this.pollId) {
      clearInterval(this.pollId)
    }
  }

  public stopStreaming() {
    if (this.id) {
      const success = StreamingControllerRegistry.abortStreaming(this.id);
      if (success) {
        console.log("AgentSession: Successfully aborted streaming");
      } else {
        console.log("AgentSession: No active streaming to abort");
      }
    } else {
      console.log("AgentSession: No session ID available for stopping streaming");
    }
  }

}
