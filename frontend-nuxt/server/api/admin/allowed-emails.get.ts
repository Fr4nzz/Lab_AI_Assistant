import { getAllowedEmails } from '../../utils/adminConfig'
import { requireAdmin } from '../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

  return {
    emails: getAllowedEmails()
  }
})
