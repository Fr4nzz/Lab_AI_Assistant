import axios from 'axios'

const API_BASE = '/api'

export interface Chat {
  id: string
  title: string | null
  created_at: string
  updated_at?: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  attachments?: { filename: string; type: string }[]
  created_at: string
}

export interface ExtractedField {
  field: string
  value: string
  unit?: string
}

export interface ExtractedData {
  patient: string
  exam: string
  fields: ExtractedField[]
}

export interface PlanStep {
  action: string
  description?: string
  element_index?: number
  text?: string
  url?: string
}

export interface Suggestion {
  type: string
  message: string
  apply: boolean
}

export interface AgentResponse {
  // New backend format
  message?: string
  status?: 'executing' | 'waiting_for_user' | 'completed' | 'error'
  tool_calls?: { tool: string; parameters: Record<string, unknown> }[]
  tool_results?: { tool: string; result: Record<string, unknown> }[]
  data_to_review?: Record<string, unknown>
  next_step?: string

  // Legacy format (kept for compatibility)
  mode?: 'question' | 'plan' | 'error' | 'message'
  question?: string
  options?: string[]
  understanding?: string
  extracted_data?: ExtractedData[]
  steps?: PlanStep[]
  suggestions?: Suggestion[]
  error?: string
}

export interface ExecutionResult {
  success: boolean
  message: string
  results?: { step: number; action: string; success: boolean; error?: string }[]
}

const api = {
  // Chats
  async getChats(): Promise<Chat[]> {
    const res = await axios.get(`${API_BASE}/chats`)
    return res.data
  },

  async createChat(title?: string): Promise<Chat> {
    const res = await axios.post(`${API_BASE}/chats`, { title })
    return res.data
  },

  async deleteChat(chatId: string): Promise<void> {
    await axios.delete(`${API_BASE}/chats/${chatId}`)
  },

  async getChatHistory(chatId: string): Promise<Message[]> {
    const res = await axios.get(`${API_BASE}/chats/${chatId}/history`)
    return res.data
  },

  // Messages
  async sendMessage(chatId: string, message: string, files?: File[]): Promise<AgentResponse> {
    const formData = new FormData()
    formData.append('chat_id', chatId)
    formData.append('message', message)
    
    if (files) {
      files.forEach(file => formData.append('files', file))
    }

    const res = await axios.post(`${API_BASE}/chat`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return res.data
  },

  // Plan execution
  async executePlan(chatId: string, plan: { steps: PlanStep[]; extracted_data: ExtractedData[] }): Promise<ExecutionResult> {
    const res = await axios.post(`${API_BASE}/execute`, { chat_id: chatId, plan })
    return res.data
  },

  // Browser
  async getBrowserState(): Promise<{ url: string; title: string; elements: unknown[] }> {
    const res = await axios.get(`${API_BASE}/browser/state`)
    return res.data
  },

  async getScreenshot(): Promise<string> {
    const res = await axios.get(`${API_BASE}/browser/screenshot`)
    return res.data.screenshot
  }
}

export default api
