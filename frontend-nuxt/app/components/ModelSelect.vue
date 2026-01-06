<script setup lang="ts">
const {
  settings,
  isLoading,
  loadSettings,
  setChatModel,
  setPreprocessingModel,
  setThinkingLevel,
  currentChatModel,
  currentPreprocessingModel,
  currentThinkingLevel,
  CHAT_MODELS,
  PREPROCESSING_MODELS,
  THINKING_LEVELS
} = useSettings()

// Load settings on mount
onMounted(() => {
  loadSettings()
})

// Items for dropdowns
const chatModelItems = computed(() => CHAT_MODELS.map(m => ({
  label: m.name,
  value: m.id,
  icon: m.icon
})))

const preprocessingModelItems = computed(() => PREPROCESSING_MODELS.map(m => ({
  label: m.name,
  value: m.id,
  icon: m.icon
})))

const thinkingLevelItems = computed(() => THINKING_LEVELS.map(l => ({
  label: l.name,
  value: l.id,
  icon: l.icon
})))

// Handlers
function handleChatModelChange(value: string) {
  setChatModel(value)
}

function handlePreprocessingModelChange(value: string) {
  setPreprocessingModel(value)
}

function handleThinkingLevelChange(value: string) {
  setThinkingLevel(value)
}
</script>

<template>
  <div class="flex items-center gap-2">
    <!-- Main Chat Model -->
    <USelectMenu
      :model-value="settings.chatModel"
      :items="chatModelItems"
      size="sm"
      :icon="currentChatModel?.icon"
      variant="ghost"
      value-key="value"
      class="hover:bg-default focus:bg-default data-[state=open]:bg-default"
      :ui="{
        trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200'
      }"
      :disabled="isLoading"
      @update:model-value="handleChatModelChange"
    />

    <!-- Preprocessing Model -->
    <UPopover>
      <UButton
        icon="i-lucide-settings-2"
        size="sm"
        variant="ghost"
        class="hover:bg-default"
        :disabled="isLoading"
      />
      <template #content>
        <div class="p-3 space-y-3 min-w-[240px]">
          <div class="text-sm font-medium text-default-500 border-b border-default pb-2">
            Preprocessing Settings
          </div>

          <!-- Preprocessing Model -->
          <div class="space-y-1">
            <label class="text-xs text-default-400">Preprocessing Model</label>
            <USelectMenu
              :model-value="settings.preprocessingModel"
              :items="preprocessingModelItems"
              size="sm"
              :icon="currentPreprocessingModel?.icon"
              value-key="value"
              class="w-full"
              :disabled="isLoading"
              @update:model-value="handlePreprocessingModelChange"
            />
          </div>

          <!-- Thinking Level -->
          <div class="space-y-1">
            <label class="text-xs text-default-400">Thinking Level</label>
            <USelectMenu
              :model-value="settings.thinkingLevel"
              :items="thinkingLevelItems"
              size="sm"
              :icon="currentThinkingLevel?.icon"
              value-key="value"
              class="w-full"
              :disabled="isLoading"
              @update:model-value="handleThinkingLevelChange"
            />
          </div>
        </div>
      </template>
    </UPopover>
  </div>
</template>
