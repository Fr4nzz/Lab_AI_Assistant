'use client';

import { useState, useCallback } from 'react';
import { Chat } from '@/components/chat';
import { ChatSidebar, ChatItem } from '@/components/chat-sidebar';

export default function Home() {
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);

  const createNewChat = useCallback(() => {
    const newChat: ChatItem = {
      id: crypto.randomUUID(),
      title: 'Nuevo Chat',
      createdAt: new Date(),
    };
    setChats((prev) => [newChat, ...prev]);
    setSelectedChatId(newChat.id);
  }, []);

  const handleTitleGenerated = useCallback((title: string) => {
    if (selectedChatId) {
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === selectedChatId ? { ...chat, title } : chat
        )
      );
    }
  }, [selectedChatId]);

  const deleteChat = useCallback((id: string) => {
    setChats((prev) => prev.filter((chat) => chat.id !== id));
    if (selectedChatId === id) {
      setSelectedChatId(null);
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
        {selectedChatId ? (
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
