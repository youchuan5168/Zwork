// 领域 API 门面：组件不再拼接业务 URL。
import api from './index'

function crud(path) {
  return {
    list: () => api.get(path),
    create: (body) => api.post(path, body),
    update: (id, body) => api.put(`${path}/${id}`, body),
    remove: (id) => api.delete(`${path}/${id}`),
  }
}

export const applicationApi = {
  ...crud('/applications'),
  changeStage: (id, stage) => api.patch(`/applications/${id}/stage`, { stage }),
  history: (id) => api.get(`/applications/${id}/stages`),
}
export const companyApi = crud('/companies')
export const scheduleApi = crud('/schedules')
export const profileApi = {
  documents: () => api.get('/profile/documents'),
  document: (id) => api.get(`/profile/documents/${id}`),
  versions: (id) => api.get(`/profile/documents/${id}/versions`),
  version: (id, number) => api.get(`/profile/documents/${id}/versions/${number}`),
  createDocument: (body) => api.post('/profile/documents', body),
  reviseDocument: (id, body) => api.post(`/profile/documents/${id}/versions`, body),
  setDefault: (id) => api.patch(`/profile/documents/${id}/default`),
  duplicateResume: (id, body) => api.post(`/profile/documents/${id}/duplicate`, body),
  profileSuggestions: (id) => api.get(`/profile/documents/${id}/profile-suggestions`),
  importDocument: (form, id = null) => api.post(
    id == null ? '/profile/documents/import' : `/profile/documents/${id}/import`, form,
    { timeout: 30000 },
  ),
  deleteDocument: (id) => api.delete(`/profile/documents/${id}`),
  search: (q, kind) => api.get('/profile/documents/search', { params: { q, kind: kind || undefined } }),
  memories: () => api.get('/profile/memories'),
  createMemory: (body) => api.post('/profile/memories', body),
  updateMemory: (id, body) => api.put(`/profile/memories/${id}`, body),
  deleteMemory: (id) => api.delete(`/profile/memories/${id}`),
  match: (resume_document_id, jd_document_id) => api.post('/profile/match', {
    resume_document_id, jd_document_id,
  }),
}
export const agentApi = {
  capabilities: () => api.get('/agent/capabilities'),
  list: () => api.get('/agent/runs'),
  create: (body) => api.post('/agent/runs', body),
  get: (id) => api.get(`/agent/runs/${id}`),
  remove: (id) => api.delete(`/agent/runs/${id}`),
  execute: (id) => api.post(`/agent/runs/${id}/execute`, null, { timeout: 0 }),
  decide: (id, body) => api.post(`/agent/runs/${id}/approval`, body),
  cancel: (id) => api.post(`/agent/runs/${id}/cancel`),
  events: (id, after = -1) => new EventSource(`/api/agent/runs/${id}/events?after=${after}`, { withCredentials: true }),
}
export const careerApi = {
  briefing: (day) => api.get('/career/briefing', { params: { day } }),
  weekly: (start) => api.get('/career/weekly', { params: { start } }),
  tasks: () => api.get('/career/tasks'),
  createTask: (body) => api.post('/career/tasks', body),
  updateTask: (id, body) => api.put(`/career/tasks/${id}`, body),
  setTaskDone: (id, done) => api.patch(`/career/tasks/${id}/done`, { done }),
  deleteTask: (id) => api.delete(`/career/tasks/${id}`),
  reviews: () => api.get('/career/reviews'),
  createReview: (body) => api.post('/career/reviews', body),
  updateReview: (id, body) => api.put(`/career/reviews/${id}`, body),
  deleteReview: (id) => api.delete(`/career/reviews/${id}`),
  interviewContext: (id) => api.get(`/career/interviews/${id}/context`),
  followupContext: (id) => api.get(`/career/applications/${id}/followup-context`),
}
export const authApi = {
  me: () => api.get('/auth/me'),
  policy: () => api.get('/auth/policy'),
  logout: () => api.post('/auth/logout'),
  changePassword: (body) => api.post('/auth/password', body),
  login: (username, password) => {
    const body = new URLSearchParams({ username, password })
    return api.post('/auth/login', body)
  },
  register: (username, password) => api.post('/auth/register', { username, password }),
}
export const settingsApi = {
  llm: () => api.get('/settings/llm'),
  saveLlm: (body) => api.put('/settings/llm', body),
  deleteLlm: () => api.delete('/settings/llm'),
}
