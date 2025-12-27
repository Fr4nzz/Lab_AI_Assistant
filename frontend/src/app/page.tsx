'use client';

import { useState, useCallback, useEffect } from 'react';
import { Chat } from '@/components/chat';
import { ChatItem } from '@/components/chat-sidebar';
import { AppSidebar, MobileHeader } from '@/components/app-sidebar';
import { ToolToggles, ALL_TOOL_IDS } from '@/components/tool-toggles';
import { BrowserTabsPanel } from '@/components/browser-tabs-panel';
import { TabEditor } from '@/components/tab-editor';
import { ModelSelector } from '@/components/model-selector';
import { useIsMobile } from '@/hooks/use-media-query';
import { ModelId, DEFAULT_MODEL } from '@/lib/models';

export default function Home() {
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [enabledTools, setEnabledTools] = useState<string[]>(ALL_TOOL_IDS);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [showTabEditor, setShowTabEditor] = useState(false);
  const [renderMarkdown, setRenderMarkdown] = useState(true);
  const [showStats, setShowStats] = useState(true);
  const [selectedModel, setSelectedModel] = useState<ModelId>(DEFAULT_MODEL);
  const isMobile = useIsMobile();

  // Collapse right panel on mobile by default
  useEffect(() => {
    if (isMobile) {
      setRightPanelCollapsed(true);
    }
  }, [isMobile]);

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

  // Get selected chat title for mobile header
  const selectedChat = chats.find(c => c.id === selectedChatId);

  return (
    <main className="h-dvh flex overflow-hidden">
      {/* Left Sidebar - Chat List (responsive) */}
      <AppSidebar
        chats={chats}
        selectedId={selectedChatId}
        onSelect={setSelectedChatId}
        onNewChat={createNewChat}
        onDelete={deleteChat}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <MobileHeader title={selectedChat?.title} />

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
            showStats={showStats}
            model={selectedModel}
          />
        )}
      </div>

      {/* Right Panel - Tools & Browser Tabs (hidden on mobile when collapsed) */}
      {(!isMobile || !rightPanelCollapsed) && (
        <aside className={`border-l flex-shrink-0 flex flex-col transition-all duration-200 ${
          rightPanelCollapsed ? 'w-12' : isMobile ? 'fixed inset-y-0 right-0 w-64 bg-background z-40' : 'w-64'
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
            <div className="border-b p-3 space-y-3">
              <h3 className="font-semibold text-sm">Ajustes</h3>

              {/* Model Selector */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Modelo</label>
                <ModelSelector
                  value={selectedModel}
                  onChange={setSelectedModel}
                  className="w-full text-xs h-8"
                />
              </div>

              {/* Markdown Toggle */}
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={renderMarkdown}
                  onChange={(e) => setRenderMarkdown(e.target.checked)}
                  className="rounded"
                />
                Renderizar Markdown
              </label>

              {/* Stats Toggle */}
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={showStats}
                  onChange={(e) => setShowStats(e.target.checked)}
                  className="rounded"
                />
                Mostrar estadísticas (tokens, costo)
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
      )}

      {/* Mobile: Backdrop when right panel is open */}
      {isMobile && !rightPanelCollapsed && (
        <div
          className="fixed inset-0 bg-black/50 z-30"
          onClick={() => setRightPanelCollapsed(true)}
        />
      )}

      {/* Mobile: Floating button to open right panel when collapsed */}
      {isMobile && rightPanelCollapsed && (
        <button
          onClick={() => setRightPanelCollapsed(false)}
          className="fixed bottom-20 right-3 z-40 h-10 w-10 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center"
          title="Mostrar herramientas"
        >
          ⚙️
        </button>
      )}

      {/* Tab Editor Modal */}
      {showTabEditor && (
        <TabEditor onClose={() => setShowTabEditor(false)} />
      )}
    </main>
  );
}
