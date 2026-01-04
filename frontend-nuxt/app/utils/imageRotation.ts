/**
 * Utility functions for image rotation detection and correction.
 */

/**
 * Rotates an image by the specified degrees and returns a new base64 data URL.
 * @param imageUrl - The source image URL (can be data URL or object URL)
 * @param degrees - Rotation degrees (0, 90, 180, 270)
 * @returns Promise<string> - The rotated image as a data URL
 */
export async function rotateImage(imageUrl: string, degrees: number): Promise<string> {
  if (degrees === 0) return imageUrl

  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'

    img.onload = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')

      if (!ctx) {
        reject(new Error('Failed to get canvas context'))
        return
      }

      // Swap width/height for 90 or 270 degree rotations
      if (degrees === 90 || degrees === 270) {
        canvas.width = img.height
        canvas.height = img.width
      } else {
        canvas.width = img.width
        canvas.height = img.height
      }

      // Move to center, rotate, and draw
      ctx.translate(canvas.width / 2, canvas.height / 2)
      ctx.rotate((degrees * Math.PI) / 180)
      ctx.drawImage(img, -img.width / 2, -img.height / 2)

      // Use PNG for lossless quality - important for text-heavy images like lab orders
      // JPEG compression causes blurry text which makes OCR/vision difficult
      resolve(canvas.toDataURL('image/png'))
    }

    img.onerror = () => {
      reject(new Error('Failed to load image'))
    }

    img.src = imageUrl
  })
}

/**
 * Converts a data URL to base64 string (without the prefix).
 */
export function dataUrlToBase64(dataUrl: string): string {
  const parts = dataUrl.split(',')
  return parts[1] || ''
}

/**
 * Gets the mime type from a data URL.
 */
export function getMimeTypeFromDataUrl(dataUrl: string): string {
  const match = dataUrl.match(/^data:([^;]+);/)
  return match ? match[1] : 'image/jpeg'
}
