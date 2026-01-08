/**
 * Image segmentation utility for splitting images into a 3x3 grid.
 * This helps AI models see details better by providing zoomed-in views.
 */

interface SegmentedImage {
  full: string  // Full image base64
  segments: string[]  // 9 segments (3x3 grid) as base64
  labels: string[]  // Labels for each segment: "top-left", "top-center", etc.
}

/**
 * Segment an image into a 3x3 grid.
 * @param base64Data - Base64 encoded image data (without data URL prefix)
 * @param mimeType - MIME type of the image (e.g., 'image/jpeg')
 * @returns Promise with full image and 9 segments
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

        const segmentWidth = Math.floor(img.width / 3)
        const segmentHeight = Math.floor(img.height / 3)

        // Create a canvas for each segment
        for (let row = 0; row < 3; row++) {
          for (let col = 0; col < 3; col++) {
            const canvas = document.createElement('canvas')
            canvas.width = segmentWidth
            canvas.height = segmentHeight

            const ctx = canvas.getContext('2d')
            if (!ctx) {
              reject(new Error('Could not get canvas context'))
              return
            }

            // Draw the segment
            ctx.drawImage(
              img,
              col * segmentWidth,  // Source X
              row * segmentHeight, // Source Y
              segmentWidth,        // Source width
              segmentHeight,       // Source height
              0,                   // Dest X
              0,                   // Dest Y
              segmentWidth,        // Dest width
              segmentHeight        // Dest height
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
