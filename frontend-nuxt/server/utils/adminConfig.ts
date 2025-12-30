import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'

// Config file path (in data directory to persist across restarts)
const CONFIG_FILE = join(process.cwd(), 'data', 'admin-config.json')

interface AdminConfig {
  allowedEmails: string[]
  lastUpdated: string
}

function ensureDataDir() {
  const dir = dirname(CONFIG_FILE)
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true })
  }
}

function loadConfig(): AdminConfig {
  ensureDataDir()

  if (existsSync(CONFIG_FILE)) {
    try {
      const data = readFileSync(CONFIG_FILE, 'utf-8')
      return JSON.parse(data)
    } catch {
      console.warn('[AdminConfig] Could not parse config file, using defaults')
    }
  }

  // Initialize from env vars if no config file exists
  const config = useRuntimeConfig()
  const envEmails = config.allowedEmails
    ? config.allowedEmails.split(',').map((e: string) => e.trim().toLowerCase()).filter(Boolean)
    : []

  const initialConfig: AdminConfig = {
    allowedEmails: envEmails,
    lastUpdated: new Date().toISOString()
  }

  // Save initial config
  saveConfig(initialConfig)
  return initialConfig
}

function saveConfig(config: AdminConfig) {
  ensureDataDir()
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2))
}

// In-memory cache
let cachedConfig: AdminConfig | null = null

export function getAllowedEmails(): string[] {
  if (!cachedConfig) {
    cachedConfig = loadConfig()
  }
  return cachedConfig.allowedEmails
}

export function addAllowedEmail(email: string): boolean {
  const normalized = email.trim().toLowerCase()
  if (!normalized) return false

  if (!cachedConfig) {
    cachedConfig = loadConfig()
  }

  if (cachedConfig.allowedEmails.includes(normalized)) {
    return false // Already exists
  }

  cachedConfig.allowedEmails.push(normalized)
  cachedConfig.lastUpdated = new Date().toISOString()
  saveConfig(cachedConfig)
  return true
}

export function removeAllowedEmail(email: string): boolean {
  const normalized = email.trim().toLowerCase()

  if (!cachedConfig) {
    cachedConfig = loadConfig()
  }

  const index = cachedConfig.allowedEmails.indexOf(normalized)
  if (index === -1) {
    return false // Not found
  }

  cachedConfig.allowedEmails.splice(index, 1)
  cachedConfig.lastUpdated = new Date().toISOString()
  saveConfig(cachedConfig)
  return true
}

export function isAllowedEmail(email: string): boolean {
  const normalized = email.trim().toLowerCase()
  const allowed = getAllowedEmails()

  // If no allowed emails configured, allow all
  if (allowed.length === 0) {
    return true
  }

  return allowed.includes(normalized)
}

export function isAdminEmail(email: string): boolean {
  const config = useRuntimeConfig()
  const adminEmails = config.adminEmails
    ? config.adminEmails.split(',').map((e: string) => e.trim().toLowerCase())
    : []

  return adminEmails.includes(email.trim().toLowerCase())
}

export function getAdminEmails(): string[] {
  const config = useRuntimeConfig()
  return config.adminEmails
    ? config.adminEmails.split(',').map((e: string) => e.trim().toLowerCase()).filter(Boolean)
    : []
}
