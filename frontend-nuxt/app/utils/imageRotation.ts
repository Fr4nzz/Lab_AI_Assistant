/**
 * Image Rotation Utility
 * Functions for rotating images using canvas and detecting rotation with AI
 */

export type RotationDegrees = 0 | 90 | 180 | 270

export interface RotationResult {
  rotation: RotationDegrees
  model: string | null
  success: boolean
  error?: string
  timing?: { modelMs?: number; totalMs?: number }
}

export interface RotatedImageResult {
  originalFile: File
  rotatedFile: File | null
  rotatedDataUrl: string | null
  rotation: RotationDegrees
  wasRotated: boolean
  model?: string | null
  timing?: { modelMs?: number; totalMs?: number }
}

/**
 * Convert a File to a data URL
 */
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * Convert a data URL to a File
 */
export function dataUrlToFile(dataUrl: string, fileName: string): File {
  const arr = dataUrl.split(',')
  const mime = arr[0].match(/:(.*?);/)?.[1] || 'image/png'
  const bstr = atob(arr[1])
  let n = bstr.length
  const u8arr = new Uint8Array(n)
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n)
  }
  return new File([u8arr], fileName, { type: mime })
}

/**
 * Rotate an image by the specified degrees using canvas
 * @param imageDataUrl - The image as a data URL
 * @param degrees - Rotation in degrees (0, 90, 180, 270)
 * @returns Rotated image as data URL
 */
export function rotateImage(imageDataUrl: string, degrees: RotationDegrees): Promise<string> {
  return new Promise((resolve, reject) => {
    if (degrees === 0) {
      resolve(imageDataUrl)
      return
    }

    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')

      if (!ctx) {
        reject(new Error('Could not get canvas context'))
        return
      }

      // Set canvas dimensions based on rotation
      if (degrees === 90 || degrees === 270) {
        canvas.width = img.height
        canvas.height = img.width
      } else {
        canvas.width = img.width
        canvas.height = img.height
      }

      // Move to center, rotate, then draw
      ctx.translate(canvas.width / 2, canvas.height / 2)
      ctx.rotate((degrees * Math.PI) / 180)
      ctx.drawImage(img, -img.width / 2, -img.height / 2)

      // Get the rotated image as data URL
      resolve(canvas.toDataURL('image/jpeg', 0.92))
    }
    img.onerror = () => reject(new Error('Failed to load image for rotation'))
    img.src = imageDataUrl
  })
}

/**
 * Detect if an image needs rotation using the AI API
 * @param imageDataUrl - The image as a data URL
 * @returns Rotation detection result
 */
export async function detectRotation(imageDataUrl: string): Promise<RotationResult> {
  try {
    const response = await $fetch<RotationResult>('/api/detect-rotation', {
      method: 'POST',
      body: {
        imageDataUrl
      }
    })
    return response
  } catch (error) {
    console.error('Failed to detect rotation:', error)
    return {
      rotation: 0,
      model: null,
      success: false,
      error: (error as Error).message
    }
  }
}

/**
 * Process an image file: detect rotation and rotate if needed
 * @param file - The image file to process
 * @returns The processed image result
 */
export async function processImageRotation(file: File): Promise<RotatedImageResult> {
  // Only process image files
  if (!file.type.startsWith('image/')) {
    return {
      originalFile: file,
      rotatedFile: null,
      rotatedDataUrl: null,
      rotation: 0,
      wasRotated: false
    }
  }

  try {
    // Convert file to data URL
    const dataUrl = await fileToDataUrl(file)

    // Detect rotation
    const detection = await detectRotation(dataUrl)

    // If no rotation needed, return original
    if (detection.rotation === 0 || !detection.success) {
      return {
        originalFile: file,
        rotatedFile: null,
        rotatedDataUrl: null,
        rotation: detection.rotation,
        wasRotated: false,
        model: detection.model,
        timing: detection.timing
      }
    }

    // Rotate the image
    const rotatedDataUrl = await rotateImage(dataUrl, detection.rotation)

    // Create a new file from the rotated image
    const rotatedFileName = file.name.replace(/(\.[^.]+)$/, `-rotated-${detection.rotation}$1`)
    const rotatedFile = dataUrlToFile(rotatedDataUrl, rotatedFileName)

    return {
      originalFile: file,
      rotatedFile,
      rotatedDataUrl,
      rotation: detection.rotation,
      wasRotated: true,
      model: detection.model,
      timing: detection.timing
    }
  } catch (error) {
    console.error('Failed to process image rotation:', error)
    return {
      originalFile: file,
      rotatedFile: null,
      rotatedDataUrl: null,
      rotation: 0,
      wasRotated: false
    }
  }
}

/**
 * Process multiple image files for rotation
 * @param files - Array of files to process
 * @returns Array of processed results
 */
export async function processImagesRotation(files: File[]): Promise<RotatedImageResult[]> {
  const imageFiles = files.filter(f => f.type.startsWith('image/'))
  const nonImageFiles = files.filter(f => !f.type.startsWith('image/'))

  // Process images in parallel
  const imageResults = await Promise.all(
    imageFiles.map(file => processImageRotation(file))
  )

  // Add non-image files as-is
  const nonImageResults: RotatedImageResult[] = nonImageFiles.map(file => ({
    originalFile: file,
    rotatedFile: null,
    rotatedDataUrl: null,
    rotation: 0 as RotationDegrees,
    wasRotated: false
  }))

  return [...imageResults, ...nonImageResults]
}
