import browser from "webextension-polyfill"
import { Agent } from "./agent"

export const findAllAgents = async (): Promise<Agent[]> => {
  let { agents } = await browser.storage.local.get("agents")
  if (!agents) {
    agents = []
    await updateAgents(agents)
  }
  return agents.map((a: any) => Agent.fromJsonObject(a))
}

export const findAgentById = async (agentId: string): Promise<Agent | undefined> => {
  let agents = await findAllAgents()
  return agents.find(a => a.manifest.id === agentId)
}

export const addAgent = async (agent: Agent): Promise<void> => {
  let agents = await findAllAgents()
  if (agents.find(a => a.manifest.id === agent.manifest.id)) {
    throw new ExistingAgentError()
  }
  agents.push(agent)
  agents.sort((a1, a2) => a1.manifest.id < a2.manifest.id ? -1 : 1)
  await updateAgents(agents)
}

export class ExistingAgentError extends Error {
}

const updateAgents = async (agents: Agent[]) => {
  await browser.storage.local.set({ agents: agents })
}

export const removeAgent = async (agentId: string): Promise<void> => {
  let agents = await findAllAgents()
  agents = agents.filter(a => a.manifest.id !== agentId)
  await updateAgents(agents)
}

export const setAgentThinkingMode = async (agentId: string, hasThinkingMode: boolean): Promise<void> => {
  const key = `agent_thinking_mode_${agentId}`
  console.log(`Setting thinking mode for agent ${agentId}: ${hasThinkingMode}`);
  await browser.storage.local.set({ [key]: hasThinkingMode })
}

export const getAgentThinkingMode = async (agentId: string): Promise<boolean> => {
  const key = `agent_thinking_mode_${agentId}`
  const result = await browser.storage.local.get(key)
  const hasThinkingMode = result[key] || false
  return hasThinkingMode
}

export const getUserThinkingModePreference = async (agentId: string): Promise<boolean> => {
  const key = `user_thinking_mode_${agentId}`
  const result = await browser.storage.local.get(key)
  return result[key] || false
}

export const setUserThinkingModePreference = async (agentId: string, enabled: boolean): Promise<void> => {
  const key = `user_thinking_mode_${agentId}`
  await browser.storage.local.set({ [key]: enabled })
}
