'use client';

import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { useState, useRef, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ChatProps {
  chatId?: string;
  onTitleGenerated?: (title: string) => void;
}

export function Chat({ chatId, onTitleGenerated }: ChatProps) {
  const [enabledTools] = useState<string[]>([
    'search_orders', 'get_order_results', 'get_order_info',
    'edit_results', 'edit_order_exams', 'create_new_order',
    'get_available_exams', 'ask_user'
  ]);
  const [input, setInput] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [titleGenerated, setTitleGenerated] = useState(false);

  // Create transport with custom body
  const transport = useMemo(() => new DefaultChatTransport({
    api: '/api/chat',
    body: { enabledTools },
  }), [enabledTools]);

  const { messages, sendMessage, status, error } = useChat({
    transport,
    id: chatId,
    onError: (err) => {
      console.error('[Chat] onError:', err);
    },
    onFinish: async () => {
      console.log('[Chat] onFinish called, messages:', messages.length);
      // Generate title for new chats (only once)
      if (messages.length === 1 && !titleGenerated && onTitleGenerated) {
        setTitleGenerated(true);
        try {
          const res = await fetch('/api/chat/title', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: messages[0]?.parts
                .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
                .map(p => p.text)
                .join('') || ''
            }),
          });
          const { title } = await res.json();
          onTitleGenerated(title);
        } catch (e) {
          console.error('Failed to generate title:', e);
        }
      }
    },
  });

  // Debug: log messages and status changes
  useEffect(() => {
    console.log('[Chat] Messages changed:', messages.length, 'Status:', status);
    messages.forEach((m, i) => {
      const content = m.parts?.map(p => p.type === 'text' ? (p as {type: 'text', text: string}).text?.slice(0, 50) : p.type).join(', ');
      console.log(`[Chat] Message ${i}: role=${m.role}, parts=${m.parts?.length}, content=${content}`);
    });
  }, [messages, status]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Reset title generation flag when chat changes
  useEffect(() => {
    setTitleGenerated(false);
  }, [chatId]);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() && !fileInputRef.current?.files?.length) return;

    const files = fileInputRef.current?.files;
    const messageContent = input.trim();

    // Clear input immediately
    setInput('');

    // Clear file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    // Send message
    console.log('[Chat] Sending message:', messageContent.slice(0, 50));
    try {
      if (files && files.length > 0) {
        await sendMessage({
          text: messageContent,
          files: files,
        });
      } else {
        await sendMessage({
          text: messageContent,
        });
      }
      console.log('[Chat] sendMessage completed');
    } catch (err) {
      console.error('[Chat] sendMessage error:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleFormSubmit(e as unknown as React.FormEvent);
    }
  };

  // Get text content from message parts
  const getMessageContent = (message: typeof messages[0]) => {
    return message.parts
      .filter((part): part is { type: 'text'; text: string } => part.type === 'text')
      .map(part => part.text)
      .join('');
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4 max-w-4xl mx-auto">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground py-12">
              <h2 className="text-2xl font-bold mb-2">Lab Assistant AI</h2>
              <p>Selecciona un chat o escribe un mensaje para comenzar</p>
              <p className="text-sm mt-2">
                Puedes enviar texto, imagenes del cuaderno, o audio con instrucciones
              </p>
            </div>
          )}

          {messages.map((message) => (
            <Card
              key={message.id}
              className={`p-4 ${
                message.role === 'user'
                  ? 'bg-primary/10 ml-12'
                  : 'bg-muted mr-12'
              }`}
            >
              <div className="font-semibold mb-1 text-sm text-muted-foreground">
                {message.role === 'user' ? 'Tu' : 'Asistente'}
              </div>
              <div className="whitespace-pre-wrap">{getMessageContent(message)}</div>
            </Card>
          ))}

          {status === 'streaming' && (
            <div className="text-muted-foreground animate-pulse">
              Escribiendo...
            </div>
          )}

          {error && (
            <Card className="p-4 bg-destructive/10 border-destructive">
              <div className="text-destructive">Error: {error.message}</div>
            </Card>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t p-4">
        <form onSubmit={handleFormSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-2 items-end">
            <input
              type="file"
              ref={fileInputRef}
              multiple
              accept="image/*,.pdf,audio/*"
              className="hidden"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              disabled={status === 'streaming'}
            >
              <span className="text-lg">📎</span>
            </Button>
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Escribe un mensaje..."
              className="flex-1 min-h-[44px] max-h-[200px] resize-none"
              rows={1}
              disabled={status === 'streaming'}
            />
            <Button
              type="submit"
              disabled={status === 'streaming' || (!input.trim() && !fileInputRef.current?.files?.length)}
            >
              Enviar
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
