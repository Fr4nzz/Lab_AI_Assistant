export interface FileWithStatus {
  file: File
  id: string
  previewUrl: string
  status: 'uploading' | 'uploaded' | 'error'
  base64Data?: string
  error?: string
  // Preprocessing results
  rotation?: number
  rotatedBase64?: string  // Actually contains fully preprocessed (rotated + cropped) image
  preprocessed?: boolean
  useCrop?: boolean
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
