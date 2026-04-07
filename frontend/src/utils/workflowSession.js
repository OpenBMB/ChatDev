const LAST_WORKFLOW_STORAGE_KEY = 'moviedev.last-workflow'

const normalizeWorkflowName = (value) => {
  if (!value) {
    return ''
  }
  return String(value).replace(/\.ya?ml$/i, '').trim()
}

export const getLastWorkflowName = () => {
  if (typeof window === 'undefined') {
    return ''
  }
  try {
    return normalizeWorkflowName(window.localStorage.getItem(LAST_WORKFLOW_STORAGE_KEY))
  } catch (error) {
    console.warn('[workflowSession] Failed to read last workflow:', error)
    return ''
  }
}

export const setLastWorkflowName = (value) => {
  if (typeof window === 'undefined') {
    return
  }
  const normalized = normalizeWorkflowName(value)
  try {
    if (normalized) {
      window.localStorage.setItem(LAST_WORKFLOW_STORAGE_KEY, normalized)
    } else {
      window.localStorage.removeItem(LAST_WORKFLOW_STORAGE_KEY)
    }
  } catch (error) {
    console.warn('[workflowSession] Failed to save last workflow:', error)
  }
}

export const buildWorkflowPath = (value) => {
  const normalized = normalizeWorkflowName(value)
  return normalized ? `/workflows/${normalized}` : '/workflows'
}

export const normalizeStoredWorkflowName = normalizeWorkflowName
