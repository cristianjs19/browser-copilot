<script lang="ts" setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  thoughts?: string
  thoughtsTokens?: number
  isComplete: boolean
}>()

const { t } = useI18n()
const isThoughtsExpanded = ref(false)
const hasThoughts = computed(() => props.thoughts && props.thoughts.trim().length > 0)

/**
 * Get titles from all thought steps for collapsed preview
 */
const getThoughtsPreview = () => {
  if (!props.thoughts) return '';
  
  // Extract all titles wrapped in ** from the thoughts content
  const titleRegex = /\*\*(.*?)\*\*/g;
  const titles = [];
  let match;
  
  while ((match = titleRegex.exec(props.thoughts)) !== null) {
    titles.push(match[1].trim());
  }
  
  if (titles.length === 0) {
    // Fallback to first line if no titles found
    const firstLine = props.thoughts.split('\n')[0];
    return firstLine.length > 60 ? firstLine.substring(0, 60) + '...' : firstLine;
  }
  
  // Join titles with bullet points
  return titles.join(' • ');
};
</script>

<template>
  <div v-if="hasThoughts" class="mb-4 border border-gray-600 rounded-lg overflow-hidden">
    <button
      @click="isThoughtsExpanded = !isThoughtsExpanded"
      class="w-full px-4 py-3 text-left bg-gray-700 hover:bg-gray-650 border-b border-gray-600 flex items-center justify-between transition-colors duration-200"
    >
      <div class="flex items-center space-x-2">
        <svg 
          :class="`w-4 h-4 transition-transform duration-200 ${isThoughtsExpanded ? 'rotate-90' : ''}`"
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
        <span class="text-sm font-medium text-blue-400">{{ t('thoughtProcess') }}</span>
        <div v-if="!isThoughtsExpanded && thoughts && !isComplete" class="flex items-center space-x-1 text-blue-400">
          <div class="flex space-x-1">
            <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
            <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
            <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
          </div>
          <span class="text-sm text-blue-400 ml-2">{{ t('thinking') }}</span>
        </div>
      </div>
      <span v-if="thoughtsTokens" class="text-xs text-gray-500">
        {{ thoughtsTokens }} {{ t('thinkingTokens') }}
      </span>
    </button>
    
    <div v-if="isThoughtsExpanded" class="px-4 py-3 bg-gray-800 border-t border-gray-600">
      <div class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
        {{ thoughts }}
      </div>
    </div>
    
    <div v-if="!isThoughtsExpanded" class="px-4 py-2 bg-gray-750 text-xs text-gray-400 italic">
      {{ getThoughtsPreview() }}
    </div>
  </div>
</template>

<style scoped>
/* Animation styles are inherited from parent or can be moved here if needed */
</style>

<i18n>
{
  "en": {
    "thoughtProcess": "Thought Process",
    "thinking": "Thinking...",
    "thinkingTokens": "thinking tokens"
  },
  "es": {
    "thoughtProcess": "Proceso de Pensamiento",
    "thinking": "Pensando...",
    "thinkingTokens": "tokens de pensamiento"
  }
}
</i18n>