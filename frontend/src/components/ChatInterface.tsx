import { useState, useRef, useEffect } from 'react'
import api, { Message, ExtractedData, PlanStep, Suggestion, AgentResponse } from '../api/client'
import DataTable from './DataTable'
import PlanReview from './PlanReview'

interface Props {
  chatId: string
  onRefreshChats: () => void
}

export default function ChatInterface({ chatId, onRefreshChats }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [isLoading, setIsLoading] = useState(false)
  
  // Plan state
  const [pendingPlan, setPendingPlan] = useState<{
    understanding: string
    steps: PlanStep[]
    suggestions: Suggestion[]
  } | null>(null)
  const [extractedData, setExtractedData] = useState<ExtractedData[]>([])
  
  // Question state
  const [question, setQuestion] = useState<{ text: string; options?: string[] } | null>(null)
  
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadHistory()
    // Reset state when changing chats
    setPendingPlan(null)
    setExtractedData([])
    setQuestion(null)
  }, [chatId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadHistory = async () => {
    try {
      const history = await api.getChatHistory(chatId)
      setMessages(history)
    } catch (e) {
      console.error('Failed to load history:', e)
    }
  }

  const handleResponse = (response: AgentResponse) => {
    if (response.mode === 'error') {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `❌ Error: ${response.error}`,
        created_at: new Date().toISOString()
      }])
    } else if (response.mode === 'question') {
      setQuestion({
        text: response.question || '',
        options: response.options
      })
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.question || '',
        created_at: new Date().toISOString()
      }])
    } else if (response.mode === 'plan') {
      setPendingPlan({
        understanding: response.understanding || '',
        steps: response.steps || [],
        suggestions: response.suggestions || []
      })
      setExtractedData(response.extracted_data || [])
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.understanding || 'Plan generado. Revisa los datos a continuación.',
        created_at: new Date().toISOString()
      }])
    }
  }

  const sendMessage = async (overrideMessage?: string) => {
    const messageText = overrideMessage || input
    if (!messageText.trim() && files.length === 0) return

    setIsLoading(true)
    setQuestion(null)

    // Add user message to UI
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: messageText,
      attachments: files.map(f => ({ filename: f.name, type: f.type })),
      created_at: new Date().toISOString()
    }])

    try {
      const response = await api.sendMessage(chatId, messageText, files.length > 0 ? files : undefined)
      handleResponse(response)
      onRefreshChats()
    } catch (e) {
      console.error('Failed to send message:', e)
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: '❌ Error al enviar el mensaje. Intenta de nuevo.',
        created_at: new Date().toISOString()
      }])
    }

    setInput('')
    setFiles([])
    setIsLoading(false)
  }

  const executePlan = async () => {
    if (!pendingPlan) return

    setIsLoading(true)

    try {
      const result = await api.executePlan(chatId, {
        steps: pendingPlan.steps,
        extracted_data: extractedData
      })

      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: result.success 
          ? `✅ ${result.message}` 
          : `⚠️ ${result.message}`,
        created_at: new Date().toISOString()
      }])

      setPendingPlan(null)
      setExtractedData([])
    } catch (e) {
      console.error('Failed to execute plan:', e)
    }

    setIsLoading(false)
  }

  const cancelPlan = () => {
    setPendingPlan(null)
    setExtractedData([])
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'assistant',
      content: 'Plan cancelado. ¿Qué más puedo ayudarte?',
      created_at: new Date().toISOString()
    }])
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files))
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-interface">
      {/* Messages */}
      <div className="messages">
        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <div className="message-content">
              {msg.content}
              {msg.attachments && msg.attachments.length > 0 && (
                <div className="attachments">
                  {msg.attachments.map((a, i) => (
                    <span key={i} className="attachment-badge">
                      📎 {a.filename}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="message assistant">
            <div className="message-content loading">
              <span className="dot">.</span>
              <span className="dot">.</span>
              <span className="dot">.</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Question options */}
      {question?.options && (
        <div className="question-options">
          {question.options.map((opt, i) => (
            <button key={i} onClick={() => sendMessage(opt)}>
              {opt}
            </button>
          ))}
        </div>
      )}

      {/* Data table for editing */}
      {extractedData.length > 0 && (
        <DataTable 
          data={extractedData} 
          onChange={setExtractedData}
        />
      )}

      {/* Plan review */}
      {pendingPlan && (
        <PlanReview
          plan={pendingPlan}
          onApprove={executePlan}
          onCancel={cancelPlan}
          isLoading={isLoading}
        />
      )}

      {/* Input area */}
      <div className="input-area">
        <input
          type="file"
          ref={fileInputRef}
          multiple
          accept="image/*,audio/*"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        
        <button 
          className="attach-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
        >
          📎
        </button>
        
        {files.length > 0 && (
          <span className="file-count">{files.length} archivo(s)</span>
        )}
        
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Escribe un mensaje, o adjunta una imagen/audio..."
          disabled={isLoading}
          rows={1}
        />
        
        <button 
          className="send-btn"
          onClick={() => sendMessage()}
          disabled={isLoading || (!input.trim() && files.length === 0)}
        >
          ➤
        </button>
      </div>
    </div>
  )
}
