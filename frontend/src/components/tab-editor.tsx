'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ExamDetail {
  codigo: string;
  nombre: string;
  valor: string | null;  // Price
  estado: string | null;
  can_remove: boolean;
}

interface FieldDetail {
  key: string;
  exam: string;
  field: string;
  value: string;
  type: 'input' | 'select';
  options: string[] | null;  // Dropdown options
  ref: string | null;  // Reference values
}

interface TabState {
  paciente?: string;
  order_num?: string;
  exams?: string[];
  exams_details?: ExamDetail[];  // Full exam details with prices
  exams_count?: number;
  examenes_count?: number;
  total?: string;
  field_values?: Record<string, string>;
  fields_details?: FieldDetail[];  // Full field details with dropdown options
}

interface TabInfo {
  index: number;
  type: 'ordenes_list' | 'nueva_orden' | 'orden_edit' | 'resultados' | 'login' | 'unknown';
  id: string | null;
  paciente: string | null;
  is_new: boolean;
  active: boolean;
  instance?: number;
  state?: TabState;
  changes?: Partial<TabState>;
}

interface TabEditorProps {
  onClose: () => void;
}

const TAB_TYPE_LABELS: Record<string, string> = {
  ordenes_list: 'Lista de Órdenes',
  nueva_orden: 'Nueva Orden',
  orden_edit: 'Editar Orden',
  resultados: 'Resultados',
  login: 'Login',
  unknown: 'Otra',
};

export function TabEditor({ onClose }: TabEditorProps) {
  const [tabs, setTabs] = useState<TabInfo[]>([]);
  const [selectedTabIndex, setSelectedTabIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Editable state for the selected tab
  const [editedExams, setEditedExams] = useState<string[]>([]);
  const [editedExamsDetails, setEditedExamsDetails] = useState<ExamDetail[]>([]);
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});
  const [fieldsDetails, setFieldsDetails] = useState<FieldDetail[]>([]);
  const [newExamCode, setNewExamCode] = useState('');

  // Available exams for autocomplete
  const [availableExams, setAvailableExams] = useState<{ codigo: string; nombre: string }[]>([]);

  const fetchTabs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/browser/tabs/detailed');
      if (!response.ok) throw new Error('Failed to fetch tabs');
      const data = await response.json();
      setTabs(data.tabs || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading tabs');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchExams = useCallback(async () => {
    try {
      const response = await fetch('/api/exams');
      if (response.ok) {
        const data = await response.json();
        setAvailableExams(data.exams || []);
      }
    } catch {
      // Ignore - exams are optional
    }
  }, []);

  useEffect(() => {
    fetchTabs();
    fetchExams();
  }, [fetchTabs, fetchExams]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  // When a tab is selected, populate the editable state
  useEffect(() => {
    if (selectedTabIndex === null) {
      setEditedExams([]);
      setEditedExamsDetails([]);
      setEditedFields({});
      setFieldsDetails([]);
      return;
    }

    const tab = tabs[selectedTabIndex];
    if (!tab) return;

    const state = tab.state || {};
    setEditedExams(state.exams || []);
    setEditedExamsDetails(state.exams_details || []);
    setEditedFields(state.field_values || {});
    setFieldsDetails(state.fields_details || []);
  }, [selectedTabIndex, tabs]);

  const selectedTab = selectedTabIndex !== null ? tabs[selectedTabIndex] : null;

  // Add an exam to the list
  const addExam = () => {
    const code = newExamCode.trim().toUpperCase();
    if (!code) return;
    if (editedExams.includes(code)) {
      setError(`El examen ${code} ya está en la lista`);
      return;
    }
    setEditedExams(prev => [...prev, code]);
    setNewExamCode('');
    setError(null);
  };

  // Remove an exam from the list
  const removeExam = (code: string) => {
    setEditedExams(prev => prev.filter(e => e !== code));
  };

  // Update a field value
  const updateField = (key: string, value: string) => {
    setEditedFields(prev => ({ ...prev, [key]: value }));
  };

  // Execute manual tool call
  const executeToolCall = async (tool: string, args: Record<string, unknown>) => {
    try {
      setExecuting(true);
      setError(null);
      setSuccessMessage(null);

      const response = await fetch('/api/tools/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool, args }),
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || 'Tool execution failed');
      }

      setSuccessMessage(result.message || 'Cambios aplicados');
      // Refresh tabs after successful execution
      await fetchTabs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error executing tool');
    } finally {
      setExecuting(false);
    }
  };

  // Apply exam changes (add/remove)
  const applyExamChanges = async () => {
    if (!selectedTab || !selectedTab.id) return;

    const originalExams = selectedTab.state?.exams || [];
    const toAdd = editedExams.filter(e => !originalExams.includes(e));
    const toRemove = originalExams.filter(e => !editedExams.includes(e));

    if (toAdd.length === 0 && toRemove.length === 0) {
      setError('No hay cambios que aplicar');
      return;
    }

    await executeToolCall('edit_order_exams', {
      order_id: selectedTab.id,
      add: toAdd.length > 0 ? toAdd : undefined,
      remove: toRemove.length > 0 ? toRemove : undefined,
    });
  };

  // Apply result field changes
  const applyFieldChanges = async () => {
    if (!selectedTab || !selectedTab.id) return;

    const originalFields = selectedTab.state?.field_values || {};
    const changes: Array<{ orden: string; e: string; f: string; v: string }> = [];

    for (const [key, value] of Object.entries(editedFields)) {
      if (originalFields[key] !== value) {
        const [examName, fieldName] = key.split(':');
        changes.push({
          orden: selectedTab.id,
          e: examName,
          f: fieldName,
          v: value,
        });
      }
    }

    if (changes.length === 0) {
      setError('No hay cambios que aplicar');
      return;
    }

    await executeToolCall('edit_results', { data: changes });
  };

  // Check if there are changes
  const hasExamChanges = () => {
    if (!selectedTab?.state?.exams) return editedExams.length > 0;
    const original = selectedTab.state.exams;
    return editedExams.length !== original.length ||
      editedExams.some(e => !original.includes(e)) ||
      original.some(e => !editedExams.includes(e));
  };

  const hasFieldChanges = () => {
    if (!selectedTab?.state?.field_values) return false;
    const original = selectedTab.state.field_values;
    return Object.entries(editedFields).some(([k, v]) => original[k] !== v);
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-background rounded-lg shadow-xl max-w-5xl max-h-[90vh] w-full flex overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Left panel - Tab list */}
        <div className="w-64 border-r flex flex-col">
          <div className="p-3 border-b flex items-center justify-between">
            <h2 className="font-semibold">Pestañas</h2>
            <Button variant="ghost" size="sm" onClick={fetchTabs} disabled={loading}>
              🔄
            </Button>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              {loading && tabs.length === 0 && (
                <div className="text-sm text-muted-foreground text-center py-4">
                  Cargando...
                </div>
              )}

              {tabs.map((tab, idx) => (
                <button
                  key={idx}
                  className={`w-full text-left p-2 rounded text-sm hover:bg-muted ${
                    selectedTabIndex === idx ? 'bg-primary/10 border border-primary' : ''
                  } ${tab.active ? 'font-semibold' : ''}`}
                  onClick={() => setSelectedTabIndex(idx)}
                >
                  <div className="flex items-center gap-1">
                    <span>{TAB_TYPE_LABELS[tab.type]}</span>
                    {tab.active && <span className="text-[10px] text-primary">●</span>}
                  </div>
                  {tab.id && (
                    <div className="text-[10px] text-muted-foreground">
                      {tab.type === 'resultados' ? `#${tab.id}` : `ID: ${tab.id}`}
                    </div>
                  )}
                  {tab.paciente && (
                    <div className="text-[10px] text-muted-foreground truncate">
                      {tab.paciente}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* Right panel - Tab details & editor */}
        <div className="flex-1 flex flex-col">
          <div className="p-3 border-b flex items-center justify-between">
            <h2 className="font-semibold">
              {selectedTab ? TAB_TYPE_LABELS[selectedTab.type] : 'Selecciona una pestaña'}
            </h2>
            <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
              ✕
            </button>
          </div>

          <ScrollArea className="flex-1 p-4">
            {!selectedTab ? (
              <div className="text-center text-muted-foreground py-8">
                Selecciona una pestaña para ver y editar sus datos
              </div>
            ) : selectedTab.type === 'resultados' ? (
              // Results editor
              <div className="space-y-4">
                <div className="text-sm text-muted-foreground">
                  Paciente: <span className="font-medium text-foreground">{selectedTab.paciente || 'N/A'}</span>
                  {' | '}
                  Orden: <span className="font-medium text-foreground">#{selectedTab.id}</span>
                </div>

                <div className="space-y-2">
                  <h3 className="font-medium text-sm">Campos de Resultados</h3>
                  {fieldsDetails.length > 0 ? (
                    <div className="border rounded overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-muted">
                          <tr>
                            <th className="text-left px-3 py-2 font-medium">Examen</th>
                            <th className="text-left px-3 py-2 font-medium">Campo</th>
                            <th className="text-left px-3 py-2 font-medium">Valor</th>
                            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Ref.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fieldsDetails.map((field, idx) => {
                            const currentValue = editedFields[field.key] ?? field.value;
                            const originalValue = selectedTab.state?.field_values?.[field.key] || '';
                            const isChanged = currentValue !== originalValue;
                            return (
                              <tr key={field.key + idx} className="border-t">
                                <td className="px-3 py-2 text-xs text-muted-foreground">
                                  {field.exam}
                                </td>
                                <td className="px-3 py-2 text-xs font-medium">
                                  {field.field}
                                </td>
                                <td className="px-3 py-2">
                                  {field.type === 'select' && field.options ? (
                                    <select
                                      value={currentValue}
                                      onChange={(e) => updateField(field.key, e.target.value)}
                                      className={`w-full px-2 py-1 text-sm border rounded ${
                                        isChanged ? 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20' : ''
                                      }`}
                                    >
                                      {field.options.map((opt, i) => (
                                        <option key={i} value={opt}>{opt}</option>
                                      ))}
                                    </select>
                                  ) : (
                                    <input
                                      type="text"
                                      value={currentValue}
                                      onChange={(e) => updateField(field.key, e.target.value)}
                                      className={`w-full px-2 py-1 text-sm border rounded ${
                                        isChanged ? 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20' : ''
                                      }`}
                                    />
                                  )}
                                </td>
                                <td className="px-3 py-2 text-xs text-muted-foreground">
                                  {field.ref || '-'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground py-4 text-center">
                      No hay campos de resultados disponibles
                    </div>
                  )}
                </div>
              </div>
            ) : selectedTab.type === 'orden_edit' || selectedTab.type === 'nueva_orden' ? (
              // Order/exams editor
              <div className="space-y-4">
                {selectedTab.paciente && (
                  <div className="text-sm text-muted-foreground">
                    Paciente: <span className="font-medium text-foreground">{selectedTab.paciente}</span>
                  </div>
                )}

                <div className="space-y-3">
                  <h3 className="font-medium text-sm">Exámenes Agregados</h3>

                  {/* Exam table with details */}
                  {editedExamsDetails.length > 0 ? (
                    <div className="border rounded overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-muted">
                          <tr>
                            <th className="text-left px-3 py-2 font-medium">Código</th>
                            <th className="text-left px-3 py-2 font-medium">Nombre</th>
                            <th className="text-right px-3 py-2 font-medium">Precio</th>
                            <th className="w-10"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {editedExamsDetails.map((exam, idx) => {
                            const isRemoved = !editedExams.includes(exam.codigo);
                            return (
                              <tr
                                key={exam.codigo + idx}
                                className={`border-t ${isRemoved ? 'bg-red-50 dark:bg-red-900/10 opacity-60' : ''}`}
                              >
                                <td className={`px-3 py-2 font-mono ${isRemoved ? 'line-through' : ''}`}>
                                  {exam.codigo}
                                </td>
                                <td className={`px-3 py-2 ${isRemoved ? 'line-through' : ''}`}>
                                  {exam.nombre}
                                </td>
                                <td className={`px-3 py-2 text-right ${isRemoved ? 'line-through' : ''}`}>
                                  {exam.valor || '-'}
                                </td>
                                <td className="px-2 py-2 text-center">
                                  {isRemoved ? (
                                    <button
                                      onClick={() => setEditedExams(prev => [...prev, exam.codigo])}
                                      className="text-muted-foreground hover:text-foreground"
                                      title="Restaurar"
                                    >
                                      ↩
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => removeExam(exam.codigo)}
                                      className="text-muted-foreground hover:text-destructive"
                                      title="Quitar"
                                    >
                                      ×
                                    </button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground py-2">
                      No hay exámenes agregados
                    </div>
                  )}

                  {/* Total */}
                  {selectedTab.state?.total && (
                    <div className="flex justify-end text-sm font-medium pt-2 border-t">
                      Total: <span className="ml-2">{selectedTab.state.total}</span>
                    </div>
                  )}

                  {/* Add exam input */}
                  <div className="pt-3 border-t">
                    <h4 className="text-xs font-medium text-muted-foreground mb-2">Agregar Examen</h4>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newExamCode}
                        onChange={(e) => setNewExamCode(e.target.value.toUpperCase())}
                        onKeyDown={(e) => e.key === 'Enter' && addExam()}
                        placeholder="Código del examen (ej: BH, EMO)"
                        className="flex-1 px-2 py-1 text-sm border rounded"
                        list="exam-suggestions"
                      />
                      <datalist id="exam-suggestions">
                        {availableExams.slice(0, 20).map(exam => (
                          <option key={exam.codigo} value={exam.codigo}>
                            {exam.nombre}
                          </option>
                        ))}
                      </datalist>
                      <Button size="sm" onClick={addExam}>
                        Agregar
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center text-muted-foreground py-8">
                Este tipo de pestaña no es editable
              </div>
            )}
          </ScrollArea>

          {/* Footer with action buttons */}
          {selectedTab && (selectedTab.type === 'resultados' || selectedTab.type === 'orden_edit' || selectedTab.type === 'nueva_orden') && (
            <div className="p-3 border-t flex items-center justify-between">
              <div className="flex items-center gap-2">
                {error && (
                  <span className="text-sm text-destructive">{error}</span>
                )}
                {successMessage && (
                  <span className="text-sm text-green-600">{successMessage}</span>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditedExams(selectedTab.state?.exams || []);
                    setEditedExamsDetails(selectedTab.state?.exams_details || []);
                    setEditedFields(selectedTab.state?.field_values || {});
                    setFieldsDetails(selectedTab.state?.fields_details || []);
                    setError(null);
                    setSuccessMessage(null);
                  }}
                >
                  Descartar
                </Button>
                <Button
                  onClick={selectedTab.type === 'resultados' ? applyFieldChanges : applyExamChanges}
                  disabled={executing || (selectedTab.type === 'resultados' ? !hasFieldChanges() : !hasExamChanges())}
                >
                  {executing ? 'Aplicando...' : 'Aplicar Cambios'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
