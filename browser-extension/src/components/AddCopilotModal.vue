<script lang="ts" setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Agent } from '../scripts/agent'
import { addAgent, ExistingAgentError, setAgentThinkingMode } from '../scripts/agent-repository'
import { saveAgentPrompts } from '../scripts/prompt-repository'
import { ValidationResult } from '../scripts/validation';
import ModalForm from './ModalForm.vue'
import FormInput from './FormInput.vue'

defineProps<{ show: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void,
  (e: 'saved', prompt: Agent): void
}>()
const { t } = useI18n()
const url = ref('')
const validation = ref(ValidationResult.valid())

const save = async () => {
  try {
    let agent = await Agent.fromUrl(url.value)
    console.log(`Adding agent from ${url.value}`, agent);
    console.log("Agent capabilities:", agent.manifest.capabilities);
    
    await addAgent(agent)
    await saveAgentPrompts(agent.manifest.prompts, agent.manifest.id)
    
    // Store thinking mode capability if present in capabilities array
    const hasThinkingMode = agent.manifest.capabilities?.includes('has_thinking_mode') || false
    console.log("hasThinkingMode check result:", hasThinkingMode);
    
    if (hasThinkingMode) {
      console.log("YES IT HAS THINKING MODE");
      await setAgentThinkingMode(agent.manifest.id, true)
    } else {
      console.log("NO THINKING MODE CAPABILITY FOUND");
      await setAgentThinkingMode(agent.manifest.id, false)
    }
    
    emit('saved', agent)
  } catch (e: any) {
    console.error(`There was a problem adding agent from ${url.value}`, e)
    validation.value = ValidationResult.error(t(e instanceof ExistingAgentError ? 'existingAgentError' : 'agentAddError'))
  }
}

watch(url, () => {
  validation.value = ValidationResult.valid()
})

</script>

<template>
  <ModalForm :title="t('title')" :button-text="t('saveButton')" :show="show" @close="$emit('close')" @save="save">
    <FormInput label="URL" v-model="url" focused :validationProp="validation" />
  </ModalForm>
</template>

<i18n>
{
  "en": {
    "title": "Add Copilot",
    "saveButton": "Add",
    "existingAgentError": "You have already added a copilot with same ID. You should remove it or verify if your new copilot needs to change its ID in manifest.json",
    "agentAddError": "Could not add the copilot. Verify that you can get the manifest.json from the provided URL and that it has proper format"
  },
  "es": {
    "title": "Agregar Copiloto",
    "saveButton": "Agregar",
    "existingAgentError": "Ya agregaste un copiloto con el mismo identificador. Deberías quitar el existente o verificar si tu nuevo copiloto necesita cambiar su identificador en el manifest.json",
    "agentAddError": "No se pudo agregar el copiloto. Verifica que puedes obtener el manifest.json desde la URL provista y que el formato del mismo es el correcto"
  }
}
</i18n>
