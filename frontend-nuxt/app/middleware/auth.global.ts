export default defineNuxtRouteMiddleware((to) => {
  const { loggedIn } = useUserSession()

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
