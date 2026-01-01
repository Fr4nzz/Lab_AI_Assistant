// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@nuxtjs/mdc',
    'nuxt-auth-utils'
  ],

  devtools: {
    enabled: false
  },

  // Stable dev server configuration (works with Cloudflare tunnel)
  devServer: {
    host: '127.0.0.1',
    port: 3000
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
    },
    // Externalize native modules that can't be bundled
    externals: {
      external: ['sharp']
    }
  },

  // Vite configuration for stable HMR and dependency optimization
  vite: {
    // Pre-bundle heavy dependencies to prevent "optimized dependencies changed" reloads
    optimizeDeps: {
      include: [
        // AI SDK packages (heavy, frequently cause re-optimization)
        'ai',
        '@ai-sdk/vue',

        // Database packages
        'drizzle-orm',
        'better-sqlite3',

        // UI dependencies
        'date-fns'
      ],
      // Hold first results until static imports are crawled
      holdUntilCrawlEnd: true
    },

    // Stable HMR configuration
    server: {
      host: '127.0.0.1',
      strictPort: true,
      hmr: {
        protocol: 'ws',
        host: '127.0.0.1',
        port: 3000,
        clientPort: 3000
      },
      watch: {
        // Use polling on Windows for better reliability
        usePolling: process.platform === 'win32',
        interval: 100
      }
    }
  },

  // Runtime configuration
  runtimeConfig: {
    // Server-side only
    backendUrl: process.env.BACKEND_URL || 'http://localhost:8000',
    openrouterApiKey: process.env.OPENROUTER_API_KEY || '',
    geminiApiKey: process.env.GEMINI_API_KEY || (process.env.GEMINI_API_KEYS || '').split(',')[0] || '',
    allowedEmails: process.env.ALLOWED_EMAILS || '',
    adminEmails: process.env.ADMIN_EMAILS || '',
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
