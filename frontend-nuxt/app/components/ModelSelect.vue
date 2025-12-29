<script setup lang="ts">
const { model, models, currentModel } = useModels()

const items = computed(() => models.map(m => ({
  label: m.displayName,
  value: m.id,
  icon: m.icon
})))
</script>

<template>
  <USelectMenu
    v-model="model"
    :items="items"
    size="sm"
    :icon="currentModel.icon"
    variant="ghost"
    value-key="value"
    class="hover:bg-default focus:bg-default data-[state=open]:bg-default"
    :ui="{
      trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200'
    }"
  />
</template>
