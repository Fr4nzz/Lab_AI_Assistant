'use client';

import { useState, useEffect } from 'react';
import { ChatSidebar, ChatItem } from '@/components/chat-sidebar';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { useIsMobile } from '@/hooks/use-media-query';
import { Menu } from 'lucide-react';

interface AppSidebarProps {
  chats: ChatItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete?: (id: string) => void;
}

export function AppSidebar({
  chats,
  selectedId,
  onSelect,
  onNewChat,
  onDelete,
}: AppSidebarProps) {
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(false);

  // Close sheet when a chat is selected on mobile
  const handleSelect = (id: string) => {
    onSelect(id);
    if (isMobile) {
      setOpen(false);
    }
  };

  // Close sheet when new chat is created on mobile
  const handleNewChat = () => {
    onNewChat();
    if (isMobile) {
      setOpen(false);
    }
  };

  // Sync open state with viewport size changes
  useEffect(() => {
    if (!isMobile) {
      setOpen(false);
    }
  }, [isMobile]);

  const sidebarContent = (
    <ChatSidebar
      chats={chats}
      selectedId={selectedId}
      onSelect={handleSelect}
      onNewChat={handleNewChat}
      onDelete={onDelete}
    />
  );

  // Mobile: Use Sheet (slide-out drawer)
  if (isMobile) {
    return (
      <>
        {/* Floating menu button */}
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className="fixed top-3 left-3 z-50 h-10 w-10 shadow-md"
            >
              <Menu className="h-5 w-5" />
              <span className="sr-only">Toggle menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-72">
            {sidebarContent}
          </SheetContent>
        </Sheet>
      </>
    );
  }

  // Desktop: Static sidebar
  return (
    <aside className="w-64 border-r flex-shrink-0 h-full overflow-hidden">
      {sidebarContent}
    </aside>
  );
}

/**
 * Header component for mobile that includes the menu trigger
 */
export function MobileHeader({ title }: { title?: string }) {
  const isMobile = useIsMobile();

  if (!isMobile) return null;

  return (
    <div className="h-14 border-b flex items-center justify-center px-4">
      {/* Spacer for menu button */}
      <div className="w-10" />
      <h1 className="text-lg font-semibold flex-1 text-center truncate">
        {title || 'Lab Assistant AI'}
      </h1>
      {/* Spacer for balance */}
      <div className="w-10" />
    </div>
  );
}
