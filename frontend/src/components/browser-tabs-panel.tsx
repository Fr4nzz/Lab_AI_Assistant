'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

interface TabInfo {
  index: number;
  type: 'ordenes_list' | 'nueva_orden' | 'orden_edit' | 'resultados' | 'login' | 'unknown';
  id: string | null;
  paciente: string | null;
  is_new: boolean;
  active: boolean;
  instance?: number;
  state?: {
    exams?: string[];
    total?: string;
    examenes_count?: number;
    field_values?: Record<string, string>;
  };
  changes?: {
    field_values?: Record<string, string>;
    exams?: string[];
    total?: string;
  };
}

interface BrowserTabsPanelProps {
  collapsed?: boolean;
  onRefresh?: () => void;
}

const TAB_TYPE_LABELS: Record<string, string> = {
  ordenes_list: '📋 Lista',
  nueva_orden: '➕ Nueva Orden',
  orden_edit: '✏️ Editar Orden',
  resultados: '🔬 Resultados',
  login: '🔐 Login',
  unknown: '❓ Otra',
};

const TAB_TYPE_COLORS: Record<string, string> = {
  ordenes_list: 'bg-blue-500/10 border-blue-500/30',
  nueva_orden: 'bg-green-500/10 border-green-500/30',
  orden_edit: 'bg-yellow-500/10 border-yellow-500/30',
  resultados: 'bg-purple-500/10 border-purple-500/30',
  login: 'bg-orange-500/10 border-orange-500/30',
  unknown: 'bg-gray-500/10 border-gray-500/30',
};

export function BrowserTabsPanel({ collapsed = false, onRefresh }: BrowserTabsPanelProps) {
  const [tabs, setTabs] = useState<TabInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchTabs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/browser/tabs/detailed');
      if (!response.ok) throw new Error('Failed to fetch tabs');
      const data = await response.json();
      setTabs(data.tabs || []);
      setLastUpdate(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error');
      setTabs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchTabs();
    const interval = setInterval(fetchTabs, 5000);
    return () => clearInterval(interval);
  }, [fetchTabs]);

  const handleRefresh = () => {
    fetchTabs();
    onRefresh?.();
  };

  if (collapsed) {
    return (
      <div className="p-2">
        <div className="text-xs text-muted-foreground">
          Tabs: {tabs.length}
        </div>
      </div>
    );
  }

  return (
    <div className="p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Pestañas del Navegador</h3>
        <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={loading}>
          🔄
        </Button>
      </div>

      {error && (
        <div className="text-xs text-destructive">{error}</div>
      )}

      <ScrollArea className="h-[200px]">
        <div className="space-y-2">
          {tabs.length === 0 && !loading && (
            <div className="text-xs text-muted-foreground text-center py-4">
              No hay pestañas abiertas
            </div>
          )}

          {loading && tabs.length === 0 && (
            <div className="text-xs text-muted-foreground text-center py-4">
              Cargando...
            </div>
          )}

          {tabs.map((tab, idx) => (
            <Card
              key={`${tab.type}-${tab.id || idx}`}
              className={`p-2 border ${TAB_TYPE_COLORS[tab.type] || TAB_TYPE_COLORS.unknown} ${
                tab.active ? 'ring-2 ring-primary' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="text-xs font-medium">
                      {TAB_TYPE_LABELS[tab.type] || tab.type}
                    </span>
                    {tab.is_new && (
                      <span className="text-[10px] bg-green-500 text-white px-1 rounded">
                        NUEVA
                      </span>
                    )}
                    {tab.active && (
                      <span className="text-[10px] bg-primary text-primary-foreground px-1 rounded">
                        ACTIVA
                      </span>
                    )}
                  </div>

                  {tab.id && (
                    <div className="text-[10px] text-muted-foreground">
                      {tab.type === 'resultados' ? `#${tab.id}` : `ID: ${tab.id}`}
                      {tab.instance && tab.instance > 1 && ` (${tab.instance})`}
                    </div>
                  )}

                  {tab.paciente && (
                    <div className="text-xs truncate" title={tab.paciente}>
                      {tab.paciente}
                    </div>
                  )}

                  {/* Show state for new tabs */}
                  {tab.is_new && tab.state && (
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      {tab.state.exams && tab.state.exams.length > 0 && (
                        <div>Exámenes: {tab.state.exams.slice(0, 3).join(', ')}{tab.state.exams.length > 3 ? '...' : ''}</div>
                      )}
                      {tab.state.examenes_count !== undefined && (
                        <div>Exámenes: {tab.state.examenes_count}</div>
                      )}
                      {tab.state.total && (
                        <div>Total: ${tab.state.total}</div>
                      )}
                    </div>
                  )}

                  {/* Show changes for known tabs */}
                  {!tab.is_new && tab.changes && Object.keys(tab.changes).length > 0 && (
                    <div className="mt-1 text-[10px] text-yellow-600 dark:text-yellow-400">
                      <div className="font-medium">Cambios:</div>
                      {tab.changes.exams && (
                        <div>Exámenes: {tab.changes.exams.slice(0, 3).join(', ')}</div>
                      )}
                      {tab.changes.total && (
                        <div>Total: ${tab.changes.total}</div>
                      )}
                      {tab.changes.field_values && (
                        <div>{Object.keys(tab.changes.field_values).length} campos</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </ScrollArea>

      {lastUpdate && (
        <div className="text-[10px] text-muted-foreground text-right">
          Actualizado: {lastUpdate.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
