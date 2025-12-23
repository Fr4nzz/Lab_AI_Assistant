import { useState, useEffect } from 'react'
import api, { Chat } from './api/client'
import ChatInterface from './components/ChatInterface'
import ChatList from './components/ChatList'
import './App.css'

function App() {
  const [chats, setChats] = useState<Chat[]>([])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [showBrowser, setShowBrowser] = useState(false)
  const [browserScreenshot, setBrowserScreenshot] = useState<string | null>(null)

  useEffect(() => {
    loadChats()
  }, [])

  useEffect(() => {
    if (showBrowser) {
      const interval = setInterval(async () => {
        try {
          const screenshot = await api.getScreenshot()
          setBrowserScreenshot(screenshot)
        } catch (e) {
          console.error('Failed to get screenshot:', e)
        }
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [showBrowser])

  const loadChats = async () => {
    try {
      const data = await api.getChats()
      setChats(data)
    } catch (e) {
      console.error('Failed to load chats:', e)
    }
  }

  const createChat = async () => {
    try {
      const newChat = await api.createChat()
      setChats(prev => [newChat, ...prev])
      setCurrentChatId(newChat.id)
    } catch (e) {
      console.error('Failed to create chat:', e)
    }
  }

  const deleteChat = async (chatId: string) => {
    try {
      await api.deleteChat(chatId)
      setChats(prev => prev.filter(c => c.id !== chatId))
      if (currentChatId === chatId) {
        setCurrentChatId(null)
      }
    } catch (e) {
      console.error('Failed to delete chat:', e)
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <button className="new-chat-btn" onClick={createChat}>
          + Nuevo Chat
        </button>
        <ChatList 
          chats={chats} 
          selectedId={currentChatId} 
          onSelect={setCurrentChatId}
          onDelete={deleteChat}
        />
      </aside>

      <main className="main-content">
        {currentChatId ? (
          <ChatInterface 
            chatId={currentChatId} 
            onRefreshChats={loadChats}
          />
        ) : (
          <div className="placeholder">
            <h2>🧪 Lab Assistant AI</h2>
            <p>Selecciona un chat o crea uno nuevo para comenzar</p>
            <p className="hint">
              Puedes enviar texto, imágenes del cuaderno, o audio con instrucciones
            </p>
          </div>
        )}
      </main>

      <aside className={`browser-panel ${showBrowser ? 'open' : ''}`}>
        <button 
          className="toggle-browser" 
          onClick={() => setShowBrowser(!showBrowser)}
        >
          {showBrowser ? '→' : '←'} Navegador
        </button>
        {showBrowser && browserScreenshot && (
          <div className="browser-view">
            <img 
              src={`data:image/png;base64,${browserScreenshot}`} 
              alt="Browser view"
            />
          </div>
        )}
      </aside>
    </div>
  )
}

export default App
