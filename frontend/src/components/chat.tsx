'use client';

import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ChatProps {
  chatId?: string;
  onTitleGenerated?: (title: string) => void;
}

interface FilePreview {
  id: string;
  file: File;
  preview: string;
  type: 'image' | 'pdf' | 'audio' | 'video' | 'other';
}

// Lightbox component for viewing images full size
function ImageLightbox({
  src,
  alt,
  onClose,
}: {
  src: string;
  alt: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <button
        className="absolute top-4 right-4 text-white text-2xl hover:text-gray-300"
        onClick={onClose}
      >
        ✕
      </button>
      <img
        src={src}
        alt={alt}
        className="max-w-full max-h-full object-contain"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

// Audio player component
function AudioPlayer({ src, filename }: { src: string; filename?: string }) {
  return (
    <div className="flex items-center gap-2 bg-muted rounded-lg p-2">
      <span className="text-lg">🎤</span>
      <audio controls className="h-8 max-w-[250px]">
        <source src={src} />
        Your browser does not support the audio element.
      </audio>
      {filename && <span className="text-xs text-muted-foreground truncate max-w-[100px]">{filename}</span>}
    </div>
  );
}

// Video player component
function VideoPlayer({ src, filename }: { src: string; filename?: string }) {
  return (
    <div className="rounded-lg overflow-hidden bg-muted">
      <video controls className="max-w-[300px] max-h-[200px]">
        <source src={src} />
        Your browser does not support the video element.
      </video>
      {filename && <div className="text-xs text-muted-foreground p-1 truncate">{filename}</div>}
    </div>
  );
}

// Debug modal for viewing raw message data
function DebugModal({
  chatId,
  onClose,
}: {
  chatId: string;
  onClose: () => void;
}) {
  const [debugData, setDebugData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/db/chats/${chatId}/debug`)
      .then((res) => res.json())
      .then((data) => {
        setDebugData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load debug data:', err);
        setLoading(false);
      });
  }, [chatId]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-background rounded-lg shadow-xl max-w-4xl max-h-[80vh] w-full overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Debug: Message History</h2>
          <button className="text-muted-foreground hover:text-foreground" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="p-4 overflow-auto max-h-[calc(80vh-60px)]">
          {loading ? (
            <div className="text-center text-muted-foreground">Loading...</div>
          ) : (
            <pre className="text-xs font-mono whitespace-pre-wrap bg-muted p-4 rounded">
              {JSON.stringify(debugData, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export function Chat({ chatId, onTitleGenerated }: ChatProps) {
  const [enabledTools] = useState<string[]>([
    'search_orders', 'get_order_results', 'get_order_info',
    'edit_results', 'edit_order_exams', 'create_new_order',
    'get_available_exams', 'ask_user'
  ]);
  const [input, setInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<FilePreview[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [lightboxImage, setLightboxImage] = useState<{ src: string; alt: string } | null>(null);
  const [showDebug, setShowDebug] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const [titleGenerated, setTitleGenerated] = useState(false);

  // Create transport with custom body
  const transport = useMemo(() => new DefaultChatTransport({
    api: '/api/chat',
    body: { enabledTools, chatId },
  }), [enabledTools, chatId]);

  const { messages, sendMessage, status, error } = useChat({
    transport,
    id: chatId,
    onError: (err) => {
      console.error('[Chat] onError:', err);
    },
    onFinish: async () => {
      if (messages.length === 1 && !titleGenerated && onTitleGenerated) {
        setTitleGenerated(true);
        try {
          const res = await fetch('/api/chat/title', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: messages[0]?.parts
                ?.filter((p): p is { type: 'text'; text: string } => p.type === 'text')
                .map(p => p.text)
                .join('') ?? ''
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

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Reset state when chat changes
  useEffect(() => {
    setTitleGenerated(false);
    setSelectedFiles([]);
    setInput('');
  }, [chatId]);

  // Cleanup recording on unmount
  useEffect(() => {
    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
    };
  }, []);

  // Handle file selection
  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return;

    const newFiles: FilePreview[] = Array.from(files).map(file => {
      const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      let type: FilePreview['type'] = 'other';
      let preview = '';

      if (file.type.startsWith('image/')) {
        type = 'image';
        preview = URL.createObjectURL(file);
      } else if (file.type === 'application/pdf') {
        type = 'pdf';
      } else if (file.type.startsWith('audio/')) {
        type = 'audio';
        preview = URL.createObjectURL(file);
      } else if (file.type.startsWith('video/')) {
        type = 'video';
        preview = URL.createObjectURL(file);
      }

      return { id, file, preview, type };
    });

    setSelectedFiles(prev => [...prev, ...newFiles]);
  }, []);

  // Remove a selected file
  const removeFile = useCallback((id: string) => {
    setSelectedFiles(prev => {
      const file = prev.find(f => f.id === id);
      if (file?.preview) {
        URL.revokeObjectURL(file.preview);
      }
      return prev.filter(f => f.id !== id);
    });
  }, []);

  // Start audio recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      // Only start UI timer when recording actually begins
      mediaRecorder.onstart = () => {
        setIsRecording(true);
        setRecordingTime(0);
        recordingIntervalRef.current = setInterval(() => {
          setRecordingTime(t => t + 1);
        }, 1000);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const audioFile = new File([audioBlob], `recording-${Date.now()}.webm`, { type: 'audio/webm' });
        const preview = URL.createObjectURL(audioBlob);

        setSelectedFiles(prev => [...prev, {
          id: `${Date.now()}-audio`,
          file: audioFile,
          preview,
          type: 'audio'
        }]);

        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
    } catch (err) {
      console.error('Microphone access denied:', err);
      alert('No se pudo acceder al micrófono');
    }
  };

  // Stop audio recording
  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
        recordingIntervalRef.current = null;
      }
    }
  };

  // Format recording time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle form submit
  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() && selectedFiles.length === 0) return;

    const messageContent = input.trim();
    const filesToSend = selectedFiles.map(f => f.file);

    // Determine default text based on file types (only if no user text)
    let textToSend = messageContent;
    if (!messageContent && filesToSend.length > 0) {
      const hasAudio = filesToSend.some(f => f.type.startsWith('audio/'));
      const hasVideo = filesToSend.some(f => f.type.startsWith('video/'));
      const hasImage = filesToSend.some(f => f.type.startsWith('image/'));

      if (hasAudio || hasVideo) {
        // For audio/video, don't add default text - let Gemini listen/watch
        textToSend = '';
      } else if (hasImage) {
        textToSend = 'Analiza esta imagen';
      } else {
        textToSend = 'Analiza este archivo';
      }
    }

    // Clear inputs
    setInput('');
    setSelectedFiles([]);

    try {
      if (filesToSend.length > 0) {
        // Create a DataTransfer to convert File[] to FileList
        const dataTransfer = new DataTransfer();
        filesToSend.forEach(file => dataTransfer.items.add(file));

        await sendMessage({
          text: textToSend,
          files: dataTransfer.files,
        });
      } else {
        await sendMessage({
          text: messageContent,
        });
      }
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

  // Get file parts from message
  const getMessageFiles = (message: typeof messages[0]) => {
    return message.parts
      .filter(part => part.type === 'file')
      .map(part => {
        const filePart = part as { type: 'file'; url?: string; data?: string; mimeType?: string; mediaType?: string; name?: string };
        return {
          url: filePart.url || (filePart.data ? `data:${filePart.mimeType || filePart.mediaType};base64,${filePart.data}` : ''),
          mimeType: filePart.mimeType || filePart.mediaType || '',
          name: filePart.name,
        };
      })
      .filter(f => f.url);
  };

  // Render attachment based on type
  const renderAttachment = (file: { url: string; mimeType?: string; name?: string }, idx: number) => {
    const mimeType = file.mimeType || '';

    if (mimeType.startsWith('image/')) {
      return (
        <img
          key={idx}
          src={file.url}
          alt={file.name || `Image ${idx + 1}`}
          className="max-w-[200px] max-h-[200px] rounded object-cover cursor-pointer hover:opacity-90 transition-opacity"
          onClick={() => setLightboxImage({ src: file.url, alt: file.name || `Image ${idx + 1}` })}
        />
      );
    }

    if (mimeType.startsWith('audio/')) {
      return <AudioPlayer key={idx} src={file.url} filename={file.name} />;
    }

    if (mimeType.startsWith('video/')) {
      return <VideoPlayer key={idx} src={file.url} filename={file.name} />;
    }

    // Default file icon
    return (
      <div key={idx} className="flex items-center gap-2 bg-muted rounded p-2">
        <span className="text-lg">📄</span>
        <span className="text-sm truncate max-w-[150px]">{file.name || 'File'}</span>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Lightbox */}
      {lightboxImage && (
        <ImageLightbox
          src={lightboxImage.src}
          alt={lightboxImage.alt}
          onClose={() => setLightboxImage(null)}
        />
      )}

      {/* Debug Modal */}
      {showDebug && chatId && (
        <DebugModal chatId={chatId} onClose={() => setShowDebug(false)} />
      )}

      {/* Header with debug button */}
      <div className="flex items-center justify-between px-4 py-2 border-b">
        <h1 className="text-lg font-semibold">Lab Assistant AI</h1>
        {chatId && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDebug(true)}
            title="Ver mensajes raw (debug)"
          >
            🔍 Debug
          </Button>
        )}
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4 max-w-4xl mx-auto">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground py-12">
              <h2 className="text-2xl font-bold mb-2">Lab Assistant AI</h2>
              <p>Selecciona un chat o escribe un mensaje para comenzar</p>
              <p className="text-sm mt-2">
                Puedes enviar texto, imágenes del cuaderno, audio o video con instrucciones
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
              {/* Display file attachments */}
              {getMessageFiles(message).length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {getMessageFiles(message).map((file, idx) => renderAttachment(file, idx))}
                </div>
              )}
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

      {/* File Previews */}
      {selectedFiles.length > 0 && (
        <div className="border-t px-4 py-2">
          <div className="max-w-4xl mx-auto flex flex-wrap gap-2">
            {selectedFiles.map((file) => (
              <div key={file.id} className="relative group">
                {file.type === 'image' ? (
                  <img
                    src={file.preview}
                    alt={file.file.name}
                    className="w-16 h-16 object-cover rounded border cursor-pointer"
                    onClick={() => setLightboxImage({ src: file.preview, alt: file.file.name })}
                  />
                ) : file.type === 'audio' ? (
                  <div className="w-16 h-16 bg-muted rounded border flex items-center justify-center">
                    <span className="text-2xl">🎤</span>
                  </div>
                ) : file.type === 'video' ? (
                  <div className="w-16 h-16 bg-muted rounded border flex items-center justify-center">
                    <span className="text-2xl">🎬</span>
                  </div>
                ) : file.type === 'pdf' ? (
                  <div className="w-16 h-16 bg-muted rounded border flex items-center justify-center">
                    <span className="text-2xl">📄</span>
                  </div>
                ) : (
                  <div className="w-16 h-16 bg-muted rounded border flex items-center justify-center">
                    <span className="text-2xl">📎</span>
                  </div>
                )}
                {/* Remove button */}
                <button
                  type="button"
                  onClick={() => removeFile(file.id)}
                  className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ✕
                </button>
                {/* File name tooltip */}
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-black text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
                  {file.file.name.slice(0, 20)}{file.file.name.length > 20 ? '...' : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t p-4">
        <form onSubmit={handleFormSubmit} className="max-w-4xl mx-auto">
          {/* Hidden file inputs */}
          <input
            type="file"
            ref={fileInputRef}
            multiple
            accept="image/*,.pdf,audio/*,video/*"
            className="hidden"
            onChange={(e) => handleFileSelect(e.target.files)}
          />
          <input
            type="file"
            ref={cameraInputRef}
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => handleFileSelect(e.target.files)}
          />

          <div className="flex gap-2 items-end">
            {/* Attach file button */}
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              disabled={status === 'streaming'}
              title="Adjuntar archivo"
            >
              <span className="text-lg">📎</span>
            </Button>

            {/* Camera button */}
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => cameraInputRef.current?.click()}
              disabled={status === 'streaming'}
              title="Tomar foto"
            >
              <span className="text-lg">📷</span>
            </Button>

            {/* Audio recording button */}
            <Button
              type="button"
              variant={isRecording ? "destructive" : "outline"}
              size="icon"
              onClick={isRecording ? stopRecording : startRecording}
              disabled={status === 'streaming'}
              title={isRecording ? "Detener grabación" : "Grabar audio"}
            >
              {isRecording ? (
                <span className="text-sm font-mono">{formatTime(recordingTime)}</span>
              ) : (
                <span className="text-lg">🎤</span>
              )}
            </Button>

            {/* Text input */}
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Escribe un mensaje..."
              className="flex-1 min-h-[44px] max-h-[200px] resize-none"
              rows={1}
              disabled={status === 'streaming' || isRecording}
            />

            {/* Send button */}
            <Button
              type="submit"
              disabled={status === 'streaming' || isRecording || (!input.trim() && selectedFiles.length === 0)}
            >
              Enviar
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
