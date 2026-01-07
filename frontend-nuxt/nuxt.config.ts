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

  // Stable dev server configuration (works with Cloudflare tunnel and LAN access)
  devServer: {
    host: '0.0.0.0',  // Bind to all interfaces for LAN access
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
    },
    // Route rules for headers
    routeRules: {
      '/**': {
        headers: {
          // Prevent "Look for and connect to any device on your local network" popup
          'Permissions-Policy': 'local-network=()'
        }
      }
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
        '@ai-sdk/google',

        // Database packages
        'drizzle-orm',

        // UI dependencies
        'date-fns',

        // Additional deps to reduce cold-start optimization time
        'zod',
        'nanoid'
      ],
      // Native modules can't be pre-bundled
      exclude: ['better-sqlite3'],
      // Hold first results until static imports are crawled
      holdUntilCrawlEnd: true
    },

    // Stable HMR configuration
    server: {
      host: '0.0.0.0',  // Bind to all interfaces for LAN access
      strictPort: true,
      allowedHosts: true, // Allow Cloudflare tunnel and other proxy hosts
      hmr: {
        protocol: 'ws',
        host: true,  // Auto-detect host for HMR (works with LAN and tunnels)
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
      appName: 'Lab Assistant'
      // Note: backendUrl is NOT exposed to client to avoid Local Network Access prompts
      // All backend requests go through server-side API routes
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
