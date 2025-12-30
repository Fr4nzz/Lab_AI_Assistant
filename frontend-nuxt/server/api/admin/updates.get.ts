import { execSync } from 'child_process'
import { requireAdmin } from '../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

  try {
    // Get the project root directory (parent of frontend-nuxt)
    const projectRoot = process.cwd().replace(/[/\\]frontend-nuxt$/, '')

    // Fetch latest from remote without merging
    try {
      execSync('git fetch origin', {
        cwd: projectRoot,
        timeout: 30000,
        encoding: 'utf-8'
      })
    } catch (fetchError) {
      console.warn('[Updates] Git fetch failed:', fetchError)
      // Continue anyway to check local state
    }

    // Get current branch
    const currentBranch = execSync('git rev-parse --abbrev-ref HEAD', {
      cwd: projectRoot,
      encoding: 'utf-8'
    }).trim()

    // Get local HEAD commit
    const localCommit = execSync('git rev-parse HEAD', {
      cwd: projectRoot,
      encoding: 'utf-8'
    }).trim()

    // Get remote HEAD commit for current branch
    let remoteCommit = ''
    let behindCount = 0
    let hasUpdates = false

    try {
      remoteCommit = execSync(`git rev-parse origin/${currentBranch}`, {
        cwd: projectRoot,
        encoding: 'utf-8'
      }).trim()

      // Check how many commits behind
      const behindOutput = execSync(`git rev-list HEAD..origin/${currentBranch} --count`, {
        cwd: projectRoot,
        encoding: 'utf-8'
      }).trim()

      behindCount = parseInt(behindOutput, 10) || 0
      hasUpdates = behindCount > 0
    } catch {
      // Remote branch may not exist yet
      console.warn('[Updates] Could not get remote branch info')
    }

    // Get latest commit info
    const lastCommitInfo = execSync('git log -1 --format="%H|%s|%ar|%an"', {
      cwd: projectRoot,
      encoding: 'utf-8'
    }).trim()

    const [hash, message, date, author] = lastCommitInfo.split('|')

    return {
      hasUpdates,
      currentBranch,
      localCommit: localCommit.substring(0, 7),
      remoteCommit: remoteCommit ? remoteCommit.substring(0, 7) : null,
      behindCount,
      lastCommit: {
        hash: hash?.substring(0, 7),
        message,
        date,
        author
      }
    }
  } catch (error) {
    console.error('[Updates] Error checking for updates:', error)
    throw createError({
      statusCode: 500,
      message: 'Failed to check for updates'
    })
  }
})
