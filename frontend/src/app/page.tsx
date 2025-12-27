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
  const [renderMarkdown, setRenderMarkdown] = useState(true);

  // Load chats from database on mount (don't create new chat - wait for first message)
  useEffect(() => {
    async function loadChats() {
      try {
        const response = await fetch('/api/db/chats');
        if (response.ok) {
          const data = await response.json();
          const loadedChats = data.map((chat: { id: string; title: string; createdAt: string }) => ({
            id: chat.id,
            title: chat.title,
            createdAt: new Date(chat.createdAt),
          }));
          setChats(loadedChats);
          // Don't auto-select any chat - show welcome screen
        }
      } catch (error) {
        console.error('Failed to load chats:', error);
      } finally {
        setIsLoading(false);
      }
    }
    loadChats();
  }, []);

  // Start a new chat - just clear selection, chat will be created on first message
  const createNewChat = useCallback(() => {
    setSelectedChatId(null);
  }, []);

  // Called when a new chat is created (on first message)
  const handleChatCreated = useCallback((chatId: string, title: string) => {
    console.log('[Page] handleChatCreated:', { chatId, title, currentSelectedChatId: selectedChatId });
    const newChatItem = {
      id: chatId,
      title,
      createdAt: new Date(),
    };
    setChats((prev) => [newChatItem, ...prev]);
    setSelectedChatId(chatId);
  }, [selectedChatId]);

  const handleTitleGenerated = useCallback(async (title: string, chatId?: string) => {
    const targetChatId = chatId || selectedChatId;
    console.log('[Page] handleTitleGenerated:', { title, chatId, targetChatId, selectedChatId });
    if (targetChatId) {
      // Update local state
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === targetChatId ? { ...chat, title } : chat
        )
      );
      // Update in database
      try {
        await fetch(`/api/db/chats/${targetChatId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title }),
        });
        console.log('[Page] Title updated in database for chat:', targetChatId);
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
      <aside className="w-64 border-r flex-shrink-0 h-full overflow-hidden">
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
        ) : (
          <Chat
            chatId={selectedChatId || undefined}
            onTitleGenerated={handleTitleGenerated}
            onChatCreated={handleChatCreated}
            enabledTools={enabledTools}
            renderMarkdown={renderMarkdown}
          />
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

        {/* Settings */}
        {!rightPanelCollapsed && (
          <div className="border-b p-3">
            <h3 className="font-semibold text-sm mb-2">Ajustes</h3>
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={renderMarkdown}
                onChange={(e) => setRenderMarkdown(e.target.checked)}
                className="rounded"
              />
              Renderizar Markdown
            </label>
          </div>
        )}

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
