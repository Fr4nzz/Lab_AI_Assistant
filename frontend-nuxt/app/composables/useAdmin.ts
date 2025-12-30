// Composable for admin functionality
export interface AdminStatus {
  isAdmin: boolean
  loggedIn: boolean
  email?: string
}

export interface UpdatesInfo {
  hasUpdates: boolean
  currentBranch: string
  localCommit: string
  remoteCommit: string | null
  behindCount: number
  lastCommit: {
    hash: string
    message: string
    date: string
    author: string
  }
}

export function useAdmin() {
  const adminStatus = useState<AdminStatus | null>('adminStatus', () => null)
  const allowedEmails = useState<string[]>('allowedEmails', () => [])
  const updatesInfo = useState<UpdatesInfo | null>('updatesInfo', () => null)
  const isCheckingUpdates = useState('isCheckingUpdates', () => false)
  const isUpdating = useState('isUpdating', () => false)

  const isAdmin = computed(() => adminStatus.value?.isAdmin ?? false)

  async function fetchAdminStatus() {
    try {
      const data = await $fetch<AdminStatus>('/api/admin/status')
      adminStatus.value = data
    } catch {
      adminStatus.value = { isAdmin: false, loggedIn: false }
    }
    return adminStatus.value
  }

  async function fetchAllowedEmails() {
    if (!isAdmin.value) return []

    try {
      const data = await $fetch<{ emails: string[] }>('/api/admin/allowed-emails')
      allowedEmails.value = data.emails
    } catch (error) {
      console.error('Failed to fetch allowed emails:', error)
    }
    return allowedEmails.value
  }

  async function addAllowedEmail(email: string) {
    if (!isAdmin.value) return false

    try {
      const data = await $fetch<{ emails: string[], added: boolean }>('/api/admin/allowed-emails', {
        method: 'POST',
        body: { email }
      })
      allowedEmails.value = data.emails
      return data.added
    } catch (error) {
      console.error('Failed to add email:', error)
      throw error
    }
  }

  async function removeAllowedEmail(email: string) {
    if (!isAdmin.value) return false

    try {
      const data = await $fetch<{ emails: string[], removed: boolean }>('/api/admin/allowed-emails', {
        method: 'DELETE',
        body: { email }
      })
      allowedEmails.value = data.emails
      return data.removed
    } catch (error) {
      console.error('Failed to remove email:', error)
      throw error
    }
  }

  async function checkForUpdates() {
    if (!isAdmin.value) return null

    isCheckingUpdates.value = true
    try {
      const data = await $fetch<UpdatesInfo>('/api/admin/updates')
      updatesInfo.value = data
      return data
    } catch (error) {
      console.error('Failed to check for updates:', error)
      return null
    } finally {
      isCheckingUpdates.value = false
    }
  }

  async function triggerUpdate() {
    if (!isAdmin.value) return null

    isUpdating.value = true
    try {
      const data = await $fetch('/api/admin/update', {
        method: 'POST'
      })
      return data
    } catch (error) {
      console.error('Failed to trigger update:', error)
      throw error
    } finally {
      isUpdating.value = false
    }
  }

  return {
    adminStatus,
    isAdmin,
    allowedEmails,
    updatesInfo,
    isCheckingUpdates,
    isUpdating,
    fetchAdminStatus,
    fetchAllowedEmails,
    addAllowedEmail,
    removeAllowedEmail,
    checkForUpdates,
    triggerUpdate
  }
}
