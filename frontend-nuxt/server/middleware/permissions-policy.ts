/**
 * Middleware to set Permissions-Policy header.
 * This prevents the "Look for and connect to any device on your local network" popup
 * that browsers show when WebRTC tries to gather local network candidates.
 */
export default defineEventHandler((event) => {
  // Set Permissions-Policy header to restrict local network access
  // This prevents the browser from asking for local network permission
  setResponseHeader(event, 'Permissions-Policy', 'local-network=()')
})
