'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

export interface ChatItem {
  id: string;
  title: string;
  createdAt: Date;
}

interface ChatSidebarProps {
  chats: ChatItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete?: (id: string) => void;
}

export function ChatSidebar({
  chats,
  selectedId,
  onSelect,
  onNewChat,
  onDelete,
}: ChatSidebarProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <div className="flex flex-col h-full bg-muted/50">
      <div className="p-4">
        <Button onClick={onNewChat} className="w-full">
          + Nuevo Chat
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {chats.map((chat) => (
            <div
              key={chat.id}
              className={cn(
                'flex items-center justify-between px-3 py-2 rounded-md cursor-pointer transition-colors',
                selectedId === chat.id
                  ? 'bg-primary/10 text-primary'
                  : 'hover:bg-muted'
              )}
              onClick={() => onSelect(chat.id)}
              onMouseEnter={() => setHoveredId(chat.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              <span className="truncate text-sm">{chat.title || 'Nuevo Chat'}</span>
              {hoveredId === chat.id && onDelete && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(chat.id);
                  }}
                >
                  ✕
                </Button>
              )}
            </div>
          ))}

          {chats.length === 0 && (
            <div className="text-center text-muted-foreground text-sm py-4">
              No hay chats todavia
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
