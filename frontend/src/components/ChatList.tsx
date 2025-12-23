import { Chat } from '../api/client'

interface Props {
  chats: Chat[]
  selectedId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

export default function ChatList({ chats, selectedId, onSelect, onDelete }: Props) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    if (diff < 60000) return 'Ahora'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`
    return date.toLocaleDateString('es')
  }

  return (
    <div className="chat-list">
      {chats.length === 0 ? (
        <div className="empty-list">
          No hay chats aún
        </div>
      ) : (
        chats.map(chat => (
          <div 
            key={chat.id}
            className={`chat-item ${selectedId === chat.id ? 'selected' : ''}`}
            onClick={() => onSelect(chat.id)}
          >
            <div className="chat-item-content">
              <span className="chat-title">
                {chat.title || 'Chat sin título'}
              </span>
              <span className="chat-date">
                {formatDate(chat.updated_at || chat.created_at)}
              </span>
            </div>
            <button 
              className="delete-btn"
              onClick={(e) => {
                e.stopPropagation()
                if (confirm('¿Eliminar este chat?')) {
                  onDelete(chat.id)
                }
              }}
            >
              ×
            </button>
          </div>
        ))
      )}
    </div>
  )
}
