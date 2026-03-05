import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  startConsultation,
  useInstrument,
  submitConsultation,
  type StartConsultationReq,
  type CaseInfo,
  type SubmitConsultationRes,
} from '@/api/request'

// ─── Types ────────────────────────────────────────────────────────────────────

export type MessageRole = 'doctor' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: number
}

export interface InstrumentLog {
  id: string
  action_name: string
  result_text: string
  cost: number
  timestamp: number
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useConsultationStore = defineStore('consultation', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const recordId     = ref<string>('')
  const budgetLeft   = ref<number>(0)
  const initialBudget = ref<number>(0)
  const caseInfo     = ref<CaseInfo>({})
  const caseQuestions = ref<string[]>([])
  const messages     = ref<Message[]>([])
  const instrumentLogs = ref<InstrumentLog[]>([])
  const submitResult = ref<SubmitConsultationRes | null>(null)
  const isLoading    = ref(false)
  const error        = ref<string | null>(null)

  // ── Computed ───────────────────────────────────────────────────────────────
  const budgetPercent = computed(() =>
    initialBudget.value > 0
      ? Math.max(0, Math.min(100, (budgetLeft.value / initialBudget.value) * 100))
      : 100,
  )

  const isInitialised = computed(() => recordId.value !== '')

  // ── Actions ────────────────────────────────────────────────────────────────

  async function initConsultation(payload: StartConsultationReq): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const res = await startConsultation(payload)
      recordId.value      = res.record_id
      budgetLeft.value    = res.budget_left
      initialBudget.value = res.budget_left
      caseInfo.value      = res.case_info
      caseQuestions.value = res.case_info.questions ?? []
      messages.value      = []
      instrumentLogs.value = []
      submitResult.value  = null
    } catch (err) {
      error.value = (err as Error).message
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function callInstrument(actionName: string): Promise<void> {
    if (!recordId.value) throw new Error('会话未初始化')
    isLoading.value = true
    error.value = null
    try {
      const res = await useInstrument({ record_id: recordId.value, action_name: actionName })
      budgetLeft.value = res.budget_left
      instrumentLogs.value.unshift({
        id: uid(),
        action_name: res.action_name,
        result_text: res.result,
        cost: res.cost,
        timestamp: Date.now(),
      })
    } catch (err) {
      error.value = (err as Error).message
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function submitDiagnosis(finalDiagnosis: string, doctorNotes = ''): Promise<SubmitConsultationRes> {
    if (!recordId.value) throw new Error('会话未初始化')
    isLoading.value = true
    error.value = null
    try {
      const res = await submitConsultation({ record_id: recordId.value, final_diagnosis: finalDiagnosis, doctor_notes: doctorNotes })
      submitResult.value = res
      return res
    } catch (err) {
      error.value = (err as Error).message
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // ── Message helpers (called by the component's SSE handler) ───────────────

  function addDoctorMessage(content: string): Message {
    const msg: Message = { id: uid(), role: 'doctor', content, timestamp: Date.now() }
    messages.value.push(msg)
    return msg
  }

  function addAssistantPlaceholder(): Message {
    const msg: Message = { id: uid(), role: 'assistant', content: '', timestamp: Date.now() }
    messages.value.push(msg)
    return msg
  }

  /** Appends a streamed chunk to the last assistant message.
   *  Uses index-replace to guarantee Vue's reactivity system detects the change.
   */
  function appendToLastAssistant(chunk: string): void {
    const idx = messages.value.length - 1
    if (idx < 0) return
    const last = messages.value[idx]
    if (last.role !== 'assistant') return
    // 用新对象替换数组元素，确保 Vue 反应系统捕获到变更
    messages.value[idx] = { ...last, content: last.content + chunk }
  }

  function reset(): void {
    recordId.value      = ''
    budgetLeft.value    = 0
    initialBudget.value = 0
    caseInfo.value      = {}
    caseQuestions.value = []
    messages.value      = []
    instrumentLogs.value = []
    submitResult.value  = null
    error.value         = null
  }

  return {
    // state
    recordId,
    budgetLeft,
    initialBudget,
    budgetPercent,
    caseInfo,
    caseQuestions,
    messages,
    instrumentLogs,
    submitResult,
    isLoading,
    error,
    isInitialised,
    // actions
    initConsultation,
    callInstrument,
    submitDiagnosis,
    addDoctorMessage,
    addAssistantPlaceholder,
    appendToLastAssistant,
    reset,
  }
})
