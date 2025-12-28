export interface RotationInfo {
  rotation: number // Degrees: 0, 90, 180, 270
  model: string | null
  timing: { modelMs?: number; totalMs?: number }
}

export interface FileWithStatus {
  file: File
  id: string
  previewUrl: string
  status: 'uploading' | 'uploaded' | 'error' | 'processing'
  base64Data?: string
  error?: string
  rotation?: number // Rotation in degrees (0, 90, 180, 270)
  wasRotated?: boolean
  originalFile?: File // Original file before rotation
  rotationInfo?: RotationInfo // Detailed rotation info for display
}

export const FILE_UPLOAD_CONFIG = {
  maxSize: 8 * 1024 * 1024, // 8MB
  types: ['image', 'audio', 'video', 'application/pdf', 'text/csv'],
  acceptPattern: 'image/*,audio/*,video/*,application/pdf,.csv,text/csv'
} as const

export function getFileIcon(mimeType: string, fileName?: string): string {
  if (mimeType.startsWith('image/')) return 'i-lucide-image'
  if (mimeType.startsWith('audio/')) return 'i-lucide-music'
  if (mimeType.startsWith('video/')) return 'i-lucide-video'
  if (mimeType === 'application/pdf') return 'i-lucide-file-text'
  if (mimeType === 'text/csv' || fileName?.endsWith('.csv')) return 'i-lucide-file-spreadsheet'
  return 'i-lucide-file'
}

export function removeRandomSuffix(filename: string): string {
  return filename.replace(/^(.+)-[a-zA-Z0-9]+(\.[^.]+)$/, '$1$2')
}
