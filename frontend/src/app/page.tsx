'use client';

import { useState, useCallback, useEffect } from 'react';
import { Chat } from '@/components/chat';
import { ChatSidebar, ChatItem } from '@/components/chat-sidebar';

export default function Home() {
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load chats from database on mount
  useEffect(() => {
    async function loadChats() {
      try {
        const response = await fetch('/api/db/chats');
        if (response.ok) {
          const data = await response.json();
          setChats(data.map((chat: { id: string; title: string; createdAt: string }) => ({
            id: chat.id,
            title: chat.title,
            createdAt: new Date(chat.createdAt),
          })));
        }
      } catch (error) {
        console.error('Failed to load chats:', error);
      } finally {
        setIsLoading(false);
      }
    }
    loadChats();
  }, []);

  const createNewChat = useCallback(async () => {
    try {
      const response = await fetch('/api/db/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Nuevo Chat' }),
      });
      if (response.ok) {
        const newChat = await response.json();
        setChats((prev) => [{
          id: newChat.id,
          title: newChat.title,
          createdAt: new Date(newChat.createdAt),
        }, ...prev]);
        setSelectedChatId(newChat.id);
      }
    } catch (error) {
      console.error('Failed to create chat:', error);
    }
  }, []);

  const handleTitleGenerated = useCallback(async (title: string) => {
    if (selectedChatId) {
      // Update local state
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === selectedChatId ? { ...chat, title } : chat
        )
      );
      // Update in database
      try {
        await fetch(`/api/db/chats/${selectedChatId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title }),
        });
      } catch (error) {
        console.error('Failed to update chat title:', error);
      }
    }
  }, [selectedChatId]);

  const deleteChat = useCallback(async (id: string) => {
    try {
      const response = await fetch(`/api/db/chats/${id}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        setChats((prev) => prev.filter((chat) => chat.id !== id));
        if (selectedChatId === id) {
          setSelectedChatId(null);
        }
      }
    } catch (error) {
      console.error('Failed to delete chat:', error);
    }
  }, [selectedChatId]);

  return (
    <main className="h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 border-r">
        <ChatSidebar
          chats={chats}
          selectedId={selectedChatId}
          onSelect={setSelectedChatId}
          onNewChat={createNewChat}
          onDelete={deleteChat}
        />
      </aside>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-muted-foreground">Cargando...</div>
          </div>
        ) : selectedChatId ? (
          <Chat
            chatId={selectedChatId}
            onTitleGenerated={handleTitleGenerated}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <h2 className="text-2xl font-bold mb-2">Lab Assistant AI</h2>
              <p>Selecciona un chat o crea uno nuevo para comenzar</p>
              <p className="text-sm mt-2">
                Puedes enviar texto, imagenes del cuaderno, o audio con instrucciones
              </p>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
