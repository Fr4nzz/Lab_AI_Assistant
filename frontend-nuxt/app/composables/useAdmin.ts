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

export interface ExamsUpdateInfo {
  lastUpdate: string | null
}

export interface OrdersUpdateInfo {
  lastUpdate: string | null
}

export function useAdmin() {
  const adminStatus = useState<AdminStatus | null>('adminStatus', () => null)
  const allowedEmails = useState<string[]>('allowedEmails', () => [])
  const updatesInfo = useState<UpdatesInfo | null>('updatesInfo', () => null)
  const isCheckingUpdates = useState('isCheckingUpdates', () => false)
  const isUpdating = useState('isUpdating', () => false)

  // Exams update state
  const examsLastUpdate = useState<string | null>('examsLastUpdate', () => null)
  const isUpdatingExams = useState('isUpdatingExams', () => false)

  // Orders update state
  const ordersLastUpdate = useState<string | null>('ordersLastUpdate', () => null)
  const isUpdatingOrders = useState('isUpdatingOrders', () => false)

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

  async function fetchExamsLastUpdate() {
    try {
      const data = await $fetch<ExamsUpdateInfo>('http://localhost:8000/api/exams/last-update')
      examsLastUpdate.value = data.lastUpdate
      return data.lastUpdate
    } catch (error) {
      console.error('Failed to fetch exams last update:', error)
      return null
    }
  }

  async function triggerExamsUpdate() {
    if (!isAdmin.value) return null

    isUpdatingExams.value = true
    try {
      const data = await $fetch<{ success: boolean; message: string; examCount: number; lastUpdate: string }>(
        'http://localhost:8000/api/exams/update',
        { method: 'POST', timeout: 120000 }  // 2 minute timeout for download
      )
      examsLastUpdate.value = data.lastUpdate
      return data
    } catch (error) {
      console.error('Failed to update exams list:', error)
      throw error
    } finally {
      isUpdatingExams.value = false
    }
  }

  async function fetchOrdersLastUpdate() {
    try {
      const data = await $fetch<OrdersUpdateInfo>('http://localhost:8000/api/orders/last-update')
      ordersLastUpdate.value = data.lastUpdate
      return data.lastUpdate
    } catch (error) {
      console.error('Failed to fetch orders last update:', error)
      return null
    }
  }

  async function triggerOrdersUpdate() {
    if (!isAdmin.value) return null

    isUpdatingOrders.value = true
    try {
      const data = await $fetch<{ success: boolean; message: string; orderCount: number; lastUpdate: string }>(
        'http://localhost:8000/api/orders/update',
        { method: 'POST', timeout: 180000 }  // 3 minute timeout for download (larger file)
      )
      ordersLastUpdate.value = data.lastUpdate
      return data
    } catch (error) {
      console.error('Failed to update orders list:', error)
      throw error
    } finally {
      isUpdatingOrders.value = false
    }
  }

  return {
    adminStatus,
    isAdmin,
    allowedEmails,
    updatesInfo,
    isCheckingUpdates,
    isUpdating,
    examsLastUpdate,
    isUpdatingExams,
    ordersLastUpdate,
    isUpdatingOrders,
    fetchAdminStatus,
    fetchAllowedEmails,
    addAllowedEmail,
    removeAllowedEmail,
    checkForUpdates,
    triggerUpdate,
    fetchExamsLastUpdate,
    triggerExamsUpdate,
    fetchOrdersLastUpdate,
    triggerOrdersUpdate
  }
}
