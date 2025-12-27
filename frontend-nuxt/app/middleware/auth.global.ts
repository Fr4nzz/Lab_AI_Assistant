export default defineNuxtRouteMiddleware(async (to) => {
  const { loggedIn } = useUserSession()
  const { authConfig, fetchConfig } = useAuthConfig()

  // Fetch auth config if not already loaded
  if (authConfig.value === null) {
    await fetchConfig()
  }

  // If OAuth is not configured, skip authentication entirely
  if (!authConfig.value?.oauthEnabled) {
    return
  }

  // Public routes that don't require authentication
  const publicRoutes = ['/login', '/auth']

  // Check if current route is public
  const isPublicRoute = publicRoutes.some(route => to.path.startsWith(route))

  if (isPublicRoute) {
    // If logged in and trying to access login, redirect to home
    if (loggedIn.value && to.path === '/login') {
      return navigateTo('/')
    }
    return
  }

  // Require authentication for all other routes
  if (!loggedIn.value) {
    return navigateTo('/login')
  }
})
