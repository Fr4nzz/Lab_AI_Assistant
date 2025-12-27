'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { AVAILABLE_MODELS, ModelId, getModelById } from '@/lib/models';
import { Sparkles } from 'lucide-react';

interface ModelSelectorProps {
  value: ModelId;
  onChange: (value: ModelId) => void;
  disabled?: boolean;
  className?: string;
}

export function ModelSelector({
  value,
  onChange,
  disabled,
  className,
}: ModelSelectorProps) {
  const selectedModel = getModelById(value);

  return (
    <Select
      value={value}
      onValueChange={(v) => onChange(v as ModelId)}
      disabled={disabled}
    >
      <SelectTrigger className={className}>
        <SelectValue>
          <span className="flex items-center gap-2">
            {selectedModel?.name || 'Select model'}
            {selectedModel?.free && (
              <Sparkles className="h-3 w-3 text-yellow-500" />
            )}
          </span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {AVAILABLE_MODELS.map((model) => (
          <SelectItem key={model.id} value={model.id}>
            <div className="flex items-center gap-2">
              <span>{model.name}</span>
              {model.free && (
                <Sparkles className="h-3 w-3 text-yellow-500" />
              )}
            </div>
            <div className="text-xs text-muted-foreground">
              {model.provider}
              {model.description && ` - ${model.description}`}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/**
 * Compact model selector for mobile/header use
 */
export function ModelSelectorCompact({
  value,
  onChange,
  disabled,
}: ModelSelectorProps) {
  const selectedModel = getModelById(value);

  return (
    <Select
      value={value}
      onValueChange={(v) => onChange(v as ModelId)}
      disabled={disabled}
    >
      <SelectTrigger className="h-8 w-auto min-w-[120px] text-xs">
        <SelectValue>
          <span className="flex items-center gap-1">
            {selectedModel?.name.split(' ')[0] || 'Model'}
            {selectedModel?.free && (
              <Sparkles className="h-3 w-3 text-yellow-500" />
            )}
          </span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {AVAILABLE_MODELS.map((model) => (
          <SelectItem key={model.id} value={model.id}>
            <div className="flex items-center gap-1">
              <span className="text-sm">{model.name}</span>
              {model.free && (
                <Sparkles className="h-3 w-3 text-yellow-500" />
              )}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
