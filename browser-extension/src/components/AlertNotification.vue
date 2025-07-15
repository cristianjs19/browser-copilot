<script lang="ts" setup>
import { ref, onMounted, watch } from 'vue'
import { XIcon } from 'vue-tabler-icons'

const props = defineProps<{
  show: boolean
  message: string
  type?: 'error' | 'success' | 'warning'
  autoHide?: boolean
  autoHideDelay?: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const visible = ref(false)
const timeoutId = ref<number | null>(null)

const alertClasses = {
  error: 'bg-red-50 border-red-200 text-red-800',
  success: 'bg-green-50 border-green-200 text-green-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800'
}

const iconClasses = {
  error: 'text-red-500',
  success: 'text-green-500',
  warning: 'text-yellow-500'
}

onMounted(() => {
  visible.value = props.show
})

watch(() => props.show, (newShow) => {
  visible.value = newShow
  
  if (newShow && (props.autoHide ?? true)) {
    // Clear any existing timeout
    if (timeoutId.value) {
      clearTimeout(timeoutId.value)
    }
    
    // Set new timeout
    timeoutId.value = setTimeout(() => {
      visible.value = false
      emit('close')
    }, props.autoHideDelay ?? 3000)
  }
})

const handleClose = () => {
  visible.value = false
  if (timeoutId.value) {
    clearTimeout(timeoutId.value)
    timeoutId.value = null
  }
  emit('close')
}

const alertType = props.type ?? 'error'
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 transform -translate-y-2"
    enter-to-class="opacity-100 transform translate-y-0"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 transform translate-y-0"
    leave-to-class="opacity-0 transform -translate-y-2"
  >
    <div v-if="visible" :class="`flex items-center gap-3 p-3 rounded-lg border shadow-sm ${alertClasses[alertType]}`">
      <!-- Alert Icon -->
      <div class="flex-shrink-0">
        <svg class="w-5 h-5" :class="iconClasses[alertType]" fill="currentColor" viewBox="0 0 20 20">
          <path v-if="alertType === 'error'" fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          <path v-else-if="alertType === 'success'" fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          <path v-else fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
      </div>
      
      <!-- Alert Message -->
      <div class="flex-1 text-sm font-medium">
        {{ message }}
      </div>
      
      <!-- Close Button -->
      <button 
        @click="handleClose"
        class="flex-shrink-0 p-1 rounded-full hover:bg-black hover:bg-opacity-10 transition-colors duration-200"
        :class="iconClasses[alertType]"
      >
        <XIcon class="w-4 h-4" />
      </button>
    </div>
  </Transition>
</template>