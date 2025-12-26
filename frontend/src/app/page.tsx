'use client';

import { useState, useCallback, useEffect } from 'react';
import { Chat } from '@/components/chat';
import { ChatSidebar, ChatItem } from '@/components/chat-sidebar';
import { ToolToggles, ALL_TOOL_IDS } from '@/components/tool-toggles';
import { BrowserTabsPanel } from '@/components/browser-tabs-panel';
import { TabEditor } from '@/components/tab-editor';

export default function Home() {
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [enabledTools, setEnabledTools] = useState<string[]>(ALL_TOOL_IDS);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [showTabEditor, setShowTabEditor] = useState(false);

  // Load chats from database on mount, always start with a new chat
  useEffect(() => {
    async function loadChatsAndCreateNew() {
      try {
        // Load existing chats for the sidebar
        const response = await fetch('/api/db/chats');
        if (response.ok) {
          const data = await response.json();
          const loadedChats = data.map((chat: { id: string; title: string; createdAt: string }) => ({
            id: chat.id,
            title: chat.title,
            createdAt: new Date(chat.createdAt),
          }));

          // Always create a new chat on app start
          const createResponse = await fetch('/api/db/chats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'Nuevo Chat' }),
          });
          if (createResponse.ok) {
            const newChat = await createResponse.json();
            const newChatItem = {
              id: newChat.id,
              title: newChat.title,
              createdAt: new Date(newChat.createdAt),
            };
            setChats([newChatItem, ...loadedChats]);
            setSelectedChatId(newChat.id);
          } else {
            // Fallback: just load existing chats
            setChats(loadedChats);
            if (loadedChats.length > 0) {
              setSelectedChatId(loadedChats[0].id);
            }
          }
        }
      } catch (error) {
        console.error('Failed to load chats:', error);
      } finally {
        setIsLoading(false);
      }
    }
    loadChatsAndCreateNew();
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

  const handleToolToggle = useCallback((toolId: string, enabled: boolean) => {
    setEnabledTools(prev =>
      enabled
        ? [...prev, toolId]
        : prev.filter(t => t !== toolId)
    );
  }, []);

  return (
    <main className="h-screen flex">
      {/* Left Sidebar - Chat List */}
      <aside className="w-64 border-r flex-shrink-0">
        <ChatSidebar
          chats={chats}
          selectedId={selectedChatId}
          onSelect={setSelectedChatId}
          onNewChat={createNewChat}
          onDelete={deleteChat}
        />
      </aside>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-muted-foreground">Cargando...</div>
          </div>
        ) : selectedChatId ? (
          <Chat
            chatId={selectedChatId}
            onTitleGenerated={handleTitleGenerated}
            enabledTools={enabledTools}
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

      {/* Right Panel - Tools & Browser Tabs */}
      <aside className={`border-l flex-shrink-0 flex flex-col transition-all duration-200 ${
        rightPanelCollapsed ? 'w-12' : 'w-64'
      }`}>
        {/* Toggle button */}
        <button
          onClick={() => setRightPanelCollapsed(!rightPanelCollapsed)}
          className="p-2 border-b hover:bg-muted text-xs text-muted-foreground"
          title={rightPanelCollapsed ? 'Expandir panel' : 'Colapsar panel'}
        >
          {rightPanelCollapsed ? '◀' : '▶ Colapsar'}
        </button>

        {/* Tool Toggles */}
        <div className="border-b">
          <ToolToggles
            enabledTools={enabledTools}
            onToggle={handleToolToggle}
            collapsed={rightPanelCollapsed}
          />
        </div>

        {/* Browser Tabs */}
        <div className="flex-1 overflow-hidden">
          <BrowserTabsPanel
            collapsed={rightPanelCollapsed}
            onOpenEditor={() => setShowTabEditor(true)}
          />
        </div>
      </aside>

      {/* Tab Editor Modal */}
      {showTabEditor && (
        <TabEditor onClose={() => setShowTabEditor(false)} />
      )}
    </main>
  );
}
