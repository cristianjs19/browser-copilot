<script lang="ts" setup>
import { computed, nextTick, ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/base16/gigavolt.min.css'
import MarkdownItPlantuml from 'markdown-it-plantuml'
import { ExclamationCircleIcon, CircleFilledIcon } from 'vue-tabler-icons'
import NewPromptButton from './NewPromptButton.vue'
import CopyButton from './CopyButton.vue'
import * as echarts from 'echarts'
import moment from 'moment'

const props = defineProps<{ 
  text: string, 
  file: Record<string, string>, 
  isUser: boolean, 
  isComplete: boolean, 
  isSuccess: boolean, 
  agentLogo: string, 
  agentName: string, 
  agentId: string,
  tokens?: number,
  thoughtsTokens?: number,
  thoughts?: string
}>()
const { t } = useI18n()
const renderedMsg = computed(() => props.isUser ? props.text.replaceAll('\n', '<br/>') : renderMarkDown(props.text))
const messageElement = ref<HTMLElement | null>(null);
const resizeObserver: ResizeObserver = new ResizeObserver(onResize)
var chart: any;
var prevWidth: number = 0;

// Thinking mode state
const isThoughtsExpanded = ref(false)
const hasThoughts = computed(() => !props.isUser && props.thoughts && props.thoughts.trim().length > 0)

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

function renderMarkDown(text: string) {
  let md = new MarkdownIt({
    highlight: (code: string, lang: string) => {
      let ret = code
      if (lang && hljs.getLanguage(lang)) {
        try {
          ret = hljs.highlight(code, { language: lang }).value
        } catch (__) { }
      }
      return '<pre><code class="hljs">' + ret + '</code></pre>'
    }
  })
  useTargetBlankLinks(md)
  useEcharts(md)
  md.use(MarkdownItPlantuml)
  return md.render(text)
}

function useTargetBlankLinks(md: MarkdownIt) {
  let defaultRender = md.renderer.rules.link_open || function (tokens, idx, options, env, self) {
    return self.renderToken(tokens, idx, options)
  }
  md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
    tokens[idx].attrSet('target', '_blank')
    return defaultRender(tokens, idx, options, env, self)
  }
}

function useEcharts(md: MarkdownIt) {
  const defaultRender = md.renderer.rules.fence || function (tokens, idx, options, env, self) {
    return self.renderToken(tokens, idx, options);
  };
  md.renderer.rules.fence = function (tokens, idx, options, env, self) {
    const token = tokens[idx];
    const code = token.content.trim();
    if (token.info === 'echarts') {
      nextTick().then(() => {
        const container = messageElement.value!;
        const chartDiv = container.querySelector('.echarts');
        const chartData = container.querySelector('.echarts-data');
        if (chartDiv && chartData) {
          chart = echarts.init(chartDiv as HTMLDivElement);
          const options = JSON.parse(chartData.textContent || '');
          solveEchartsFormatter(options.xAxis.axisLabel);
          solveEchartsFormatter(options.xAxis.axisPointer.label);
          chart.setOption(options);
        }
      });
      return `<div class="echarts" style="width: 100%; height: 200px;"></div><div class="echarts-data" style='display:none'>${code}</div>`;
    }
    return defaultRender(tokens, idx, options, env, self);
  };
}

function solveEchartsFormatter(obj: any) {
  if (obj && obj.formatter) {
    if (obj.formatter.name === 'formatEpoch') {
      obj.formatter = formatEpoch(obj.formatter)
    }
  }
}

function formatEpoch(config: any): (value: any) => string {
  return (value: any) => {
    if (typeof value === 'object') {
      value = value.value;
    }
    const time = moment(parseInt(value))
    return time.format(config.format);
  }
}

function onResize() {
  if (messageElement.value!.scrollWidth != prevWidth && chart) {
    prevWidth = messageElement.value!.scrollWidth;
    chart.resize();
  }
}

onMounted(() => {
  if (messageElement.value) {
    resizeObserver.observe(messageElement.value)
  }
})

onBeforeUnmount(() => {
  if (messageElement.value) {
    resizeObserver.unobserve(messageElement.value)
  }
})
</script>

<template>
  <div class="flex flex-col mb-1 p-1 min-w-7" :class="!isSuccess ? ['border-red-500', 'border-b'] : []">
    <div class="flex items-center flex-row">
      <template v-if="isUser">
        <circle-filled-icon class="text-violet-600" />
      </template>
      <template v-else-if="!isUser && isSuccess">
        <img :src="agentLogo" class="w-5 mr-1 rounded-full" />
      </template>
      <template v-else>
        <exclamation-circle-icon class="text-red-600" />
      </template>

      <span class="text-base">{{ isUser ? t('you') : agentName }}</span>
      <div class="flex-auto flex justify-end">
        <CopyButton v-if="!isUser && text" :text="text" :html="renderedMsg" />
        <NewPromptButton v-if="isUser && text" :is-large-icon="false" :text="text" :agent-id="agentId" />
      </div>
    </div>
    <div class="mt-2 ml-8 mr-2">

      <!-- Thinking mode UI -->
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
            <span class="text-sm font-medium text-blue-400">Thought Process</span>
            <div v-if="!isThoughtsExpanded && props.thoughts && !isComplete" class="flex items-center space-x-1 text-blue-400">
              <div class="flex space-x-1">
                <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
              </div>
              <span class="text-sm text-blue-400 ml-2">Thinking...</span>
            </div>
          </div>
          <span v-if="thoughtsTokens" class="text-xs text-gray-500">
            {{ thoughtsTokens }} thinking tokens
          </span>
        </button>
        
        <div v-if="isThoughtsExpanded" class="px-4 py-3 bg-gray-800 border-t border-gray-600">
          <div class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {{ props.thoughts }}
          </div>
        </div>
        
        <div v-if="!isThoughtsExpanded" class="px-4 py-2 bg-gray-750 text-xs text-gray-400 italic">
          {{ getThoughtsPreview() }}
        </div>
      </div>

      <div>
        <template v-if="file.data">
          <audio controls>
            <source :src="file.url" type="audio/webm">
          </audio>
        </template>
        <template v-if="text">
          <div v-html="renderedMsg" ref="messageElement"
            class="flex flex-col text-sm font-light leading-tight gap-2 rendered-msg" />
        </template>
      </div>
      <div class="ml-3 dot-pulse" v-if="!isComplete && !hasThoughts" />
      
      <!-- Token usage information for AI agent responses -->
      <!-- <div v-if="!isUser && isComplete && tokens !== undefined" class="mt-2 text-xs text-gray-500 flex items-center gap-2">
        <span>{{ tokens }} tokens</span>
        <span v-if="thoughtsTokens !== undefined">({{ thoughtsTokens }} thinking)</span>
      </div> -->


      <!-- Token usage Information -->
      <div v-if="!isUser && tokens" class="token-display mt-2">
        <div class="flex items-center space-x-2">
          <span>{{ tokens }} tokens</span>
          <span v-if="thoughtsTokens" class="text-blue-400">
            ({{ thoughtsTokens }} thinking)
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
<style lang="scss">
@use 'three-dots' with ($dot-width: 5px,
  $dot-height: 5px,
  $dot-color: var(--accent-color));

.rendered-msg pre {
  padding: 15px;
  background: #202126;
  border-radius: 8px;
  text-wrap: wrap;
}

// Fix: Inadequate gap between code blocks within list items.
.rendered-msg li pre {
  margin-bottom: 10px;
}

.rendered-msg pre {
  box-shadow: var(--shadow);
}

.rendered-msg pre code.hljs {
  padding: 0px;
}

div a {
  color: var(--accent-color);
  text-decoration: none;
}

.rendered-msg table {
  width: 100%;
  box-shadow: var(--shadow);
}

.rendered-msg thead tr {
  background-color: #ece6f5;
}

.rendered-msg th,
.rendered-msg td {
  padding: var(--half-spacing);
  border: var(--border);
}

.rendered-msg tbody tr:hover {
  background-color: #f1f1f1;
}

.echarts {
  box-shadow: var(--shadow);
  border-radius: var(--spacing);
  width: 100%;
  padding: var(--half-spacing);
}

.rendered-msg>img {
  box-shadow: var(--shadow);
  border-radius: var(--spacing);
  width: fit-content;
}

/* Thinking mode styles */
.dot-pulse {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.cursor-pointer {
  cursor: pointer;
}
</style>

<i18n>
{
  "en": {
    "you": "You",
    "collapse": "Collapse"
  },
  "es": {
    "you": "Tú",
    "collapse": "Colapsar"
  }
}
</i18n>
