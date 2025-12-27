// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@nuxtjs/mdc',
    'nuxt-auth-utils'
  ],

  devtools: {
    enabled: true
  },

  css: ['~/assets/css/main.css'],

  mdc: {
    headings: {
      anchorLinks: false
    },
    highlight: {
      shikiEngine: 'javascript'
    }
  },

  experimental: {
    viewTransition: true
  },

  compatibilityDate: '2024-07-11',

  nitro: {
    experimental: {
      openAPI: true
    }
  },

  // Runtime configuration
  runtimeConfig: {
    // Server-side only
    backendUrl: process.env.BACKEND_URL || 'http://localhost:8000',
    openrouterApiKey: process.env.OPENROUTER_API_KEY || '',
    allowedEmails: process.env.ALLOWED_EMAILS || '',
    databasePath: process.env.DATABASE_PATH || './data/lab-assistant.db',

    // OAuth configuration
    oauth: {
      google: {
        clientId: process.env.NUXT_OAUTH_GOOGLE_CLIENT_ID || '',
        clientSecret: process.env.NUXT_OAUTH_GOOGLE_CLIENT_SECRET || ''
      }
    },

    // Public (exposed to client)
    public: {
      appName: 'Lab Assistant',
      backendUrl: process.env.BACKEND_URL || 'http://localhost:8000'
    }
  },

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  }
})
