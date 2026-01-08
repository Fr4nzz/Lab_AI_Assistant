/**
 * Image segmentation utility for splitting images into a 3x3 grid.
 * This helps AI models see details better by providing zoomed-in views.
 *
 * Uses OVERLAPPING segments to avoid cutting handwritten text in the middle.
 * Each segment extends ~7% beyond its boundaries to capture text at borders.
 */

interface SegmentedImage {
  full: string  // Full image base64
  segments: string[]  // 9 segments (3x3 grid) as base64
  labels: string[]  // Labels for each segment: "arriba-izq", "arriba-centro", etc.
}

// Overlap factor: how much each segment extends beyond its boundaries
// 0.07 = 7% overlap on each side where possible
const OVERLAP = 0.07

/**
 * Segment an image into a 3x3 grid with overlapping boundaries.
 * @param base64Data - Base64 encoded image data (without data URL prefix)
 * @param mimeType - MIME type of the image (e.g., 'image/jpeg')
 * @returns Promise with full image and 9 overlapping segments
 */
export async function segmentImage(base64Data: string, mimeType: string): Promise<SegmentedImage> {
  return new Promise((resolve, reject) => {
    const img = new Image()

    img.onload = () => {
      try {
        const segments: string[] = []
        const labels = [
          'arriba-izq', 'arriba-centro', 'arriba-der',
          'medio-izq', 'medio-centro', 'medio-der',
          'abajo-izq', 'abajo-centro', 'abajo-der'
        ]

        const baseWidth = img.width / 3
        const baseHeight = img.height / 3

        // Create a canvas for each segment with overlap
        for (let row = 0; row < 3; row++) {
          for (let col = 0; col < 3; col++) {
            // Calculate overlapping boundaries (in relative units 0-1)
            // Each segment extends OVERLAP beyond its normal boundaries
            const startXRel = Math.max(0, col / 3 - OVERLAP)
            const endXRel = Math.min(1, (col + 1) / 3 + OVERLAP)
            const startYRel = Math.max(0, row / 3 - OVERLAP)
            const endYRel = Math.min(1, (row + 1) / 3 + OVERLAP)

            // Convert to pixel coordinates
            const srcX = Math.floor(startXRel * img.width)
            const srcY = Math.floor(startYRel * img.height)
            const srcWidth = Math.floor((endXRel - startXRel) * img.width)
            const srcHeight = Math.floor((endYRel - startYRel) * img.height)

            const canvas = document.createElement('canvas')
            canvas.width = srcWidth
            canvas.height = srcHeight

            const ctx = canvas.getContext('2d')
            if (!ctx) {
              reject(new Error('Could not get canvas context'))
              return
            }

            // Draw the overlapping segment
            ctx.drawImage(
              img,
              srcX,      // Source X
              srcY,      // Source Y
              srcWidth,  // Source width
              srcHeight, // Source height
              0,         // Dest X
              0,         // Dest Y
              srcWidth,  // Dest width
              srcHeight  // Dest height
            )

            // Get base64 data (without prefix)
            const dataUrl = canvas.toDataURL(mimeType, 0.9)
            const base64 = dataUrl.split(',')[1] || ''
            segments.push(base64)
          }
        }

        resolve({
          full: base64Data,
          segments,
          labels
        })
      } catch (error) {
        reject(error)
      }
    }

    img.onerror = () => {
      reject(new Error('Failed to load image for segmentation'))
    }

    // Load the image
    img.src = `data:${mimeType};base64,${base64Data}`
  })
}

/**
 * Convert a SegmentedImage to an array of file parts for the AI.
 * Returns: [full image, segment 1, segment 2, ..., segment 9]
 * Each segment includes a label in the text description.
 */
export function segmentedImageToParts(
  segmented: SegmentedImage,
  mimeType: string,
  fileName: string
): Array<{ type: 'file'; mediaType: string; data: string; url: string; name: string; segmentLabel?: string }> {
  const parts: Array<{ type: 'file'; mediaType: string; data: string; url: string; name: string; segmentLabel?: string }> = []

  // Add full image first
  parts.push({
    type: 'file',
    mediaType: mimeType,
    data: segmented.full,
    url: `data:${mimeType};base64,${segmented.full}`,
    name: fileName
  })

  // Add each segment with its label
  for (let i = 0; i < segmented.segments.length; i++) {
    const segment = segmented.segments[i]
    const label = segmented.labels[i]
    parts.push({
      type: 'file',
      mediaType: mimeType,
      data: segment,
      url: `data:${mimeType};base64,${segment}`,
      name: `${fileName} [${label}]`,
      segmentLabel: label
    })
  }

  return parts
}
