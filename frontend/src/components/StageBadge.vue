<script setup>
import { computed } from 'vue'

import { STAGE_MAP } from '@/constants/stages'

const props = defineProps({
  stageKey: { type: String, required: true },
})

const stage = computed(() => STAGE_MAP[props.stageKey] || { label: props.stageKey, color: '#909399', bg: '#f0f2f5' })
</script>

<template>
  <span class="stage-badge" :style="{ color: stage.color, background: stage.bg }">
    {{ stage.label }}
  </span>
</template>
