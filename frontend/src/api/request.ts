import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

// ─── Request / Response Types ───────────────────────────────────────────────

export interface StartConsultationReq {
  case_id: string
  user_id: string
}

export interface CaseInfo {
  chief_complaint?: string
  patient_name?: string
  age?: number
  gender?: string
  questions?: string[]
  [key: string]: unknown
}

export interface StartConsultationRes {
  record_id: string
  budget_left: number
  case_info: CaseInfo
}

export interface UseInstrumentReq {
  record_id: string
  action_name: string
}

export interface UseInstrumentRes {
  action_name: string
  result: string
  cost: number
  budget_left: number
}

export interface SubmitConsultationReq {
  record_id: string
  final_diagnosis: string
  doctor_notes?: string
}

export interface StandardAnswerPublic {
  diagnosis?: string
  required_instruments?: string[]
  key_findings?: Record<string, string>
}

export interface SubmitConsultationRes {
  final_score: number
  evaluation: string
  standard_answer_public?: StandardAnswerPublic
  [key: string]: unknown
}

// ─── Axios Instance ──────────────────────────────────────────────────────────

const request: AxiosInstance = axios.create({
  baseURL: 'http://localhost:28080',
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — attach auth token if present
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor — unwrap data, normalise errors
request.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error) => {
    const detail = error.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join('; ')
          : error.message ?? '网络请求失败'
    return Promise.reject(new Error(message))
  },
)

// ─── API Methods ─────────────────────────────────────────────────────────────

export const startConsultation = (
  data: StartConsultationReq,
): Promise<StartConsultationRes> => request.post('/api/consultation/start', data)

export const useInstrument = (
  data: UseInstrumentReq,
): Promise<UseInstrumentRes> => request.post('/api/consultation/instrument', data)

export const submitConsultation = (
  data: SubmitConsultationReq,
): Promise<SubmitConsultationRes> => request.post('/api/consultation/submit', data)

export default request
