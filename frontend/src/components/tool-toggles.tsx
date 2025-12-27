'use client';

import { Switch } from '@/components/ui/switch';

// Tool definitions with Spanish labels
const TOOLS = [
  { id: 'search_orders', label: 'Buscar Órdenes', description: 'Buscar órdenes por paciente o cédula' },
  { id: 'get_order_results', label: 'Ver Resultados', description: 'Obtener resultados de una orden' },
  { id: 'get_order_info', label: 'Info de Orden', description: 'Ver información de una orden' },
  { id: 'edit_results', label: 'Editar Resultados', description: 'Modificar campos de resultados' },
  { id: 'edit_order_exams', label: 'Editar Exámenes', description: 'Agregar/quitar exámenes de orden' },
  { id: 'create_new_order', label: 'Nueva Orden', description: 'Crear orden o cotización' },
  { id: 'get_available_exams', label: 'Lista Exámenes', description: 'Ver exámenes disponibles' },
  { id: 'ask_user', label: 'Preguntar', description: 'Pedir aclaración al usuario' },
] as const;

interface ToolTogglesProps {
  enabledTools: string[];
  onToggle: (toolId: string, enabled: boolean) => void;
  collapsed?: boolean;
}

export function ToolToggles({ enabledTools, onToggle, collapsed = false }: ToolTogglesProps) {
  if (collapsed) {
    return (
      <div className="p-2">
        <div className="text-xs text-muted-foreground mb-2">
          Herramientas: {enabledTools.length}/{TOOLS.length}
        </div>
      </div>
    );
  }

  return (
    <div className="p-3 space-y-3">
      <h3 className="font-semibold text-sm">Herramientas</h3>
      <div className="space-y-2">
        {TOOLS.map((tool) => {
          const isEnabled = enabledTools.includes(tool.id);
          return (
            <div key={tool.id} className="flex items-center justify-between gap-2">
              <label
                htmlFor={`tool-${tool.id}`}
                className="text-xs cursor-pointer flex-1"
                title={tool.description}
              >
                {tool.label}
              </label>
              <Switch
                id={`tool-${tool.id}`}
                checked={isEnabled}
                onCheckedChange={(checked) => onToggle(tool.id, checked)}
              />
            </div>
          );
        })}
      </div>
      <div className="pt-2 border-t flex gap-2">
        <button
          className="text-xs text-muted-foreground hover:text-foreground"
          onClick={() => TOOLS.forEach(t => onToggle(t.id, true))}
        >
          Todas
        </button>
        <button
          className="text-xs text-muted-foreground hover:text-foreground"
          onClick={() => TOOLS.forEach(t => onToggle(t.id, false))}
        >
          Ninguna
        </button>
      </div>
    </div>
  );
}

// Export tool IDs for default state
export const ALL_TOOL_IDS = TOOLS.map(t => t.id);
