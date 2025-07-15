<script lang="ts" setup>
import { ref, watch, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MicrophoneIcon, BrandTelegramIcon, PlayerStopFilledIcon, TrashXIcon, PlayerStopIcon } from 'vue-tabler-icons'
import { getPrompts, Prompt } from '../scripts/prompt-repository'
import { getAgentThinkingMode, getUserThinkingModePreference, setUserThinkingModePreference } from '../scripts/agent-repository'
import TextArea from './TextArea.vue'

const props = defineProps<{
  canSendMessage: boolean,
  supportRecording: boolean,
  agentId: string,
  isStreaming?: boolean
}>()
const emit = defineEmits<{
  (e: 'sendMessage', text: string, file: Record<string, string>): void,
  (e: 'stopStreaming'): void
}>()
const { t } = useI18n()
const inputText = ref('')
const promptList = ref<Prompt[]>([])
const selectedPromptIndex = ref(0)
const inputPosition = ref<number>()
const recordingAudio = ref(false)
const hasThinkingMode = ref(false)
const thinkingModeEnabled = ref(false)

let recordingChunks: [] = []
let recordingStream: MediaStream
let mediaRecorder: MediaRecorder

onMounted(async () => {
  console.log("ChatInput: Checking thinking mode for agent:", props.agentId);
  hasThinkingMode.value = await getAgentThinkingMode(props.agentId)
  console.log("ChatInput: hasThinkingMode result:", hasThinkingMode.value);
  
  if (hasThinkingMode.value) {
    thinkingModeEnabled.value = await getUserThinkingModePreference(props.agentId)
    console.log("ChatInput: thinkingModeEnabled from preferences:", thinkingModeEnabled.value);
  }
})

const toggleThinkingMode = async () => {
  thinkingModeEnabled.value = !thinkingModeEnabled.value
  await setUserThinkingModePreference(props.agentId, thinkingModeEnabled.value)
}

const sendMessage = () => {
  if (!props.canSendMessage) {
    return
  }
  if (inputText.value.trim() !== '') {
    emit('sendMessage', inputText.value, {})
    inputText.value = ''
  }
}

const stopStreaming = () => {
  emit('stopStreaming')
}

const canRecord = () => {
  return props.supportRecording && navigator.mediaDevices && navigator.mediaDevices.getUserMedia
}

const startRecording = async () => {
  if (!props.canSendMessage) {
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordingStream = stream;
    mediaRecorder = new MediaRecorder(recordingStream);
    mediaRecorder.start();
    recordingAudio.value = true;
    mediaRecorder.ondataavailable = (e) => {
      recordingChunks.push(e.data as never);
    };
  } catch (err) {
    console.error(`getUserMedia error: ${err}`);
  }
};

const blobToBase64 = (blob: Blob) => {
  return new Promise((resolve, _) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.readAsDataURL(blob);
  });
}

const stopRecording = () => {
  mediaRecorder.onstop = (e) => {
    recordingAudio.value = false;
  }
  stopRecorder()
}

const stopRecorder = () => {
  mediaRecorder.stop();
  recordingStream.getTracks().forEach(track => track.stop());
}

const sendAudioRecord = () => {
  mediaRecorder.onstop = (e) => {
    recordingAudio.value = false;
    const audioBlob = new Blob(recordingChunks, { type: 'audio/webm' });
    const audioObjectUrl = URL.createObjectURL(audioBlob);
    blobToBase64(audioBlob).then(result => {
      const base64WithoutTags = (result as string).substr((result as string).indexOf(',') + 1);
      emit('sendMessage', '', { data: base64WithoutTags, url: audioObjectUrl })
    })
    recordingChunks = []
  }
  stopRecorder()
}

const onKeydown = async (e: KeyboardEvent) => {
  inputPosition.value = undefined
  if (showingPromptList()) {
    if (e.key === 'Enter') {
      usePrompt(selectedPromptIndex.value, e)
    } else if (e.key === 'Escape') {
      clearPromptList()
    } else if (e.key === 'ArrowUp' && selectedPromptIndex.value > 0) {
      e.preventDefault()
      selectedPromptIndex.value--
    } else if (e.key === 'ArrowDown' && selectedPromptIndex.value < promptList.value.length - 1) {
      e.preventDefault()
      selectedPromptIndex.value++
    }
  } else if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const usePrompt = (index: number, e: UIEvent) => {
  e.preventDefault()
  let promptText = promptList.value[index].text
  let promptInputPosition = promptText.indexOf('${input}')
  if (promptInputPosition >= 0) {
    promptText = promptText.replace('${input}', '')
    inputPosition.value = promptInputPosition
  }

  inputText.value = promptText
  clearPromptList()
}

const showingPromptList = () => promptList.value.length > 0

const clearPromptList = () => {
  promptList.value = []
  selectedPromptIndex.value = 0
}

watch(inputText, async () => {
  if (!inputText.value.startsWith('/')) {
    clearPromptList()
  } else {
    await loadPromptList()
  }
})

const loadPromptList = async () => {
  promptList.value = (await getPrompts(props.agentId)).filter(p => p.name.toLowerCase().includes(inputText.value.substring(1).toLowerCase()))
}

// Computed property to determine current model
const currentModel = computed(() => {
  return thinkingModeEnabled.value ? 'Gemini 2.5 Prooo' : 'Gemini 2.5 Flashhh'
})

// Computed property to determine which UI to show
const showThinkingModeUI = computed(() => {
  return hasThinkingMode.value
})

// Computed property to determine which button to show (send or stop)
const showStopButton = computed(() => {
  return hasThinkingMode.value && props.isStreaming
})
</script>

<template>
  <div class="relative">
    <!-- STANDARD CHAT INPUT UI - for agents without thinking mode -->
    <div v-if="!showThinkingModeUI" class="flex flex-col gap-2">
      <div class="flex flex-row rounded-md p-1 border border-violet-600 shadow-sm text-xs">
        <template v-if="!recordingAudio">
          <template v-if="canRecord()">
            <button @click="startRecording" class="p-0"><microphone-icon /></button>
          </template>
          <TextArea class="w-full resize-none overflow-hidden max-h-16 border-0 outline-0 self-center"
            :placeholder="t('placeholder')" v-model="inputText" @keydown="onKeydown" focused
            :cursor-position="inputPosition" />
          <div class="flex items-center">
            <button @click="sendMessage" :disabled="!canSendMessage" 
              class="group rounded-full aspect-square bg-violet-600 hover:bg-violet-800 ml-1 disabled:opacity-50">
              <brand-telegram-icon color="white" class="group-hover:text-white" />
            </button>
          </div>
        </template>

        <template v-else>
          <button @click="sendAudioRecord"
            class="group rounded-full aspect-square border-solid p-0 border-red-500 hover:border-red-700 mr-1">
            <player-stop-filled-icon class="text-red-500 group-hover:text-red-700" />
          </button>
          <div class="text-nowrap flex items-center">{{ t('recordingAudio') }}</div>
          <div class="w-full flex items-center justify-center overflow-hidden ml-1">
            <div class="dot-floating" />
          </div>
          <button @click="stopRecording">
            <trash-x-icon />
          </button>
        </template>
      </div>
    </div>

    <!-- THINKING MODE CHAT INPUT UI - for agents with thinking mode capability -->
    <div v-else class="flex flex-col gap-2">
      <!-- Thinking Mode Toggle Section -->
      <div class="flex items-center justify-between p-2 bg-gray-50 rounded-md">
        <div class="flex items-center space-x-3">
          <span class="text-sm font-medium text-gray-700">{{ t('thinkingMode') }}</span>
          <button
            @click="toggleThinkingMode"
            :class="`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 ${
              thinkingModeEnabled ? 'bg-violet-600' : 'bg-gray-400'
            } cursor-pointer`"
          >
            <span
              :class="`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                thinkingModeEnabled ? 'translate-x-6' : 'translate-x-1'
              }`"
            />
          </button>
        </div>
        
        <!-- Model Indicator -->
        <div class="flex items-center space-x-2">
          <div :class="`w-2 h-2 rounded-full ${thinkingModeEnabled ? 'bg-violet-400' : 'bg-green-400'}`"></div>
          <span class="text-xs text-gray-500">
            {{ currentModel }}
          </span>
        </div>
      </div>

      <!-- Input Area with Dynamic Send/Stop Button -->
      <div class="flex flex-row rounded-md p-1 border border-violet-600 shadow-sm text-xs">
        <template v-if="!recordingAudio">
          <template v-if="canRecord()">
            <button @click="startRecording" class="p-0"><microphone-icon /></button>
          </template>
          <TextArea class="w-full resize-none overflow-hidden max-h-16 border-0 outline-0 self-center"
            :placeholder="t('placeholder')" v-model="inputText" @keydown="onKeydown" focused
            :cursor-position="inputPosition" />
          <div class="flex items-center">
            <!-- Stop Button - shown when streaming (works in both thinking modes) -->
            <button v-if="showStopButton" @click="stopStreaming" 
              class="group rounded-full aspect-square bg-red-600 hover:bg-red-800 ml-1">
              <player-stop-icon color="white" class="group-hover:text-white" />
            </button>
            <!-- Send Button - shown when not streaming -->
            <button v-else @click="sendMessage" :disabled="!canSendMessage"
              class="group rounded-full aspect-square bg-violet-600 hover:bg-violet-800 ml-1 disabled:opacity-50">
              <brand-telegram-icon color="white" class="group-hover:text-white" />
            </button>
          </div>
        </template>

        <template v-else>
          <button @click="sendAudioRecord"
            class="group rounded-full aspect-square border-solid p-0 border-red-500 hover:border-red-700 mr-1">
            <player-stop-filled-icon class="text-red-500 group-hover:text-red-700" />
          </button>
          <div class="text-nowrap flex items-center">{{ t('recordingAudio') }}</div>
          <div class="w-full flex items-center justify-center overflow-hidden ml-1">
            <div class="dot-floating" />
          </div>
          <button @click="stopRecording">
            <trash-x-icon />
          </button>
        </template>
      </div>
    </div>

    <!-- Prompt List (common for both modes) -->
    <div class="absolute bottom-28 z-10 rounded-md border border-violet-600 bg-white shadow-md"
      v-if="showingPromptList()">
      <div v-for="(prompt, index) in promptList" :key="prompt.name" @keydown="onKeydown"
        :class="['flex flex-row p-[5px] cursor-pointer', index === selectedPromptIndex && 'bg-violet-600 text-white']"
        @click="e => usePrompt(index, e)" @mousedown="e => e.preventDefault()">{{ prompt.name }}
      </div>
    </div>
  </div>
</template>
<i18n>
{
  "en": {
    "placeholder": "Type / to use a prompt, or type a message",
    "recordingAudio": "Recording audio",
    "thinkingMode": "Thinking Mock"
  },
  "es": {
    "placeholder": "Usa / para usar un prompt, o escribe un mensaje",
    "recordingAudio": "Grabando audio",
    "thinkingMode": "Razonamiento extendido"
  }
}
</i18n>
<style scoped>
.icon-tabler:hover {
  color: var(--accent-color);
}
</style>