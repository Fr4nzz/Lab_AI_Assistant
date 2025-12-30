import { execSync, spawn } from 'child_process'
import { requireAdmin } from '../../utils/adminAuth'

export default defineEventHandler(async (event) => {
  await requireAdmin(event)

  try {
    // Get the project root directory (parent of frontend-nuxt)
    const projectRoot = process.cwd().replace(/[/\\]frontend-nuxt$/, '')

    // Get current branch
    const currentBranch = execSync('git rev-parse --abbrev-ref HEAD', {
      cwd: projectRoot,
      encoding: 'utf-8'
    }).trim()

    let pullResult = ''
    let pullMethod = 'pull'

    // Try normal git pull first
    try {
      pullResult = execSync(`git pull origin ${currentBranch}`, {
        cwd: projectRoot,
        timeout: 60000,
        encoding: 'utf-8'
      })
    } catch (pullError: any) {
      console.warn('[Update] Normal git pull failed, trying git reset:', pullError.message)

      // If pull fails, use git reset --hard
      pullMethod = 'reset'
      try {
        // Fetch first
        execSync('git fetch origin', {
          cwd: projectRoot,
          timeout: 30000,
          encoding: 'utf-8'
        })

        // Then reset to remote
        pullResult = execSync(`git reset --hard origin/${currentBranch}`, {
          cwd: projectRoot,
          timeout: 30000,
          encoding: 'utf-8'
        })
      } catch (resetError: any) {
        throw new Error(`Both pull and reset failed: ${resetError.message}`)
      }
    }

    // Get new commit info
    const newCommitInfo = execSync('git log -1 --format="%H|%s|%ar|%an"', {
      cwd: projectRoot,
      encoding: 'utf-8'
    }).trim()

    const [hash, message, date, author] = newCommitInfo.split('|')

    // Determine platform and restart method
    const isWindows = process.platform === 'win32'

    // Schedule restart in the background
    // This gives time for the response to be sent before the server restarts
    setTimeout(() => {
      console.log('[Update] Initiating restart...')

      if (isWindows) {
        // On Windows, spawn a new process to run start-dev.bat
        // Use 'start' command to open a new window and detach
        const batPath = `${projectRoot}\\start-dev.bat`
        spawn('cmd.exe', ['/c', 'start', 'cmd.exe', '/c', batPath], {
          cwd: projectRoot,
          detached: true,
          stdio: 'ignore'
        }).unref()
      } else {
        // On Linux/Mac, use shell script or npm commands
        // First try start-dev.sh, fallback to npm commands
        try {
          spawn('bash', ['./start-dev.sh'], {
            cwd: projectRoot,
            detached: true,
            stdio: 'ignore'
          }).unref()
        } catch {
          // Fallback: just exit and let the process manager restart
          console.log('[Update] Exiting for restart...')
        }
      }

      // Exit current process after spawning the new one
      // Give a small delay for the spawn to start
      setTimeout(() => {
        process.exit(0)
      }, 1000)
    }, 500)

    return {
      success: true,
      method: pullMethod,
      result: pullResult.trim(),
      newCommit: {
        hash: hash?.substring(0, 7),
        message,
        date,
        author
      },
      message: 'Update successful! Application will restart in a few seconds...'
    }
  } catch (error: any) {
    console.error('[Update] Error updating:', error)
    throw createError({
      statusCode: 500,
      message: `Update failed: ${error.message}`
    })
  }
})
