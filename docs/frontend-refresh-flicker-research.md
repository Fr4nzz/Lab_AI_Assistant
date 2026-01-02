# Frontend Refresh & Flicker Issues Research

**Date:** January 2026
**Project:** Lab_AI_Assistant Frontend (Nuxt 4 + Vite)

## Table of Contents
1. [Observed Issues](#observed-issues)
2. [Root Causes](#root-causes)
3. [Current Configuration Analysis](#current-configuration-analysis)
4. [Proposed Solutions](#proposed-solutions)
5. [Sources](#sources)

---

## Observed Issues

### 1. URL Refreshes Until Stable
The browser URL refreshes multiple times when loading the frontend until it becomes stable.

### 2. Font Flickering (FOUT)
Text font flickers between different fonts (typically system font → custom font) during page load.

### 3. "Optimizing Dependencies" on Git Pull
When pulling changes without restarting the frontend, Vite shows "optimizing dependencies" messages and causes reloads.

---

## Root Causes

### A. Vite Dependency Pre-bundling

Vite uses esbuild to pre-bundle dependencies for faster development. When dependencies change (new packages, lockfile changes, git pull), Vite:

1. Detects the change
2. Re-optimizes affected dependencies
3. Triggers a full page reload to load new bundles

**This is expected behavior**, but it can be excessive when:
- Many dependencies are discovered dynamically during runtime
- The `node_modules/.vite` cache is invalidated frequently
- Branch switches introduce different package versions

### B. Font Loading Strategy (FOUT - Flash of Unstyled Text)

The current CSS configuration:
```css
@theme static {
  --font-sans: 'Public Sans', sans-serif;
}
```

Uses `@nuxt/fonts` module (auto-registered by Nuxt UI) which loads fonts asynchronously. This causes:
1. Browser renders with fallback `sans-serif` font
2. Custom font (`Public Sans`) downloads
3. Browser swaps fonts → visible flicker

The `font-display: swap` behavior (default) prevents invisible text but causes FOUT.

### C. HMR (Hot Module Replacement) Full Page Reloads

Several factors cause Vite to do full reloads instead of HMR:
- **Windows + Tailwind v4 + File-based routing**: Known [issue #32564](https://github.com/nuxt/nuxt/issues/32564)
- **IPv4/IPv6 mismatch**: macOS localhost resolves to `::1` (IPv6) but Vite binds to `127.0.0.1` (IPv4)
- **Custom domains/hosts**: Vite v6 security measures check Host header
- **Large CSS changes**: Tailwind regenerating styles triggers reloads

### D. ViewTransition API

The current config enables experimental view transitions:
```ts
experimental: {
  viewTransition: true
}
```

This can cause visual flickering during navigation as the browser animates between states.

---

## Current Configuration Analysis

### nuxt.config.ts Issues

```ts
// Current configuration
export default defineNuxtConfig({
  devtools: { enabled: false },           // ✅ Good - reduces overhead
  devServer: { host: '0.0.0.0' },         // ⚠️ May cause HMR issues
  experimental: { viewTransition: true }, // ⚠️ Can cause flicker
  // Missing: vite.optimizeDeps configuration
  // Missing: vite.server.hmr configuration
})
```

### Missing Configurations

1. **No `optimizeDeps.include`**: Dependencies are discovered at runtime, causing reloads
2. **No HMR configuration**: Using defaults which may not work well on all platforms
3. **No font preloading**: Fonts load on-demand causing FOUT

---

## Proposed Solutions

### Solution 1: Pre-bundle Heavy Dependencies (Reduces Reloads)

Add to `nuxt.config.ts`:

```ts
export default defineNuxtConfig({
  // ... existing config

  vite: {
    optimizeDeps: {
      include: [
        // AI SDK packages (heavy, frequently cause re-optimization)
        'ai',
        '@ai-sdk/vue',
        '@openrouter/ai-sdk-provider',

        // Database packages
        'drizzle-orm',
        'better-sqlite3',
        '@libsql/client',

        // UI dependencies
        'date-fns',

        // Nuxt UI internals that may be dynamically imported
        '@nuxt/ui > @floating-ui/vue',
        '@nuxt/ui > @headlessui/vue',
      ],
      // Hold first results until static imports are crawled
      holdUntilCrawlEnd: true,
    }
  }
})
```

**Impact:** Prevents "optimized dependencies changed" reloads by pre-bundling known heavy dependencies.

### Solution 2: Stabilize HMR Configuration (Reduces Random Reloads)

```ts
export default defineNuxtConfig({
  // ... existing config

  devServer: {
    host: '127.0.0.1',  // Changed from '0.0.0.0' - more stable
    port: 3000
  },

  vite: {
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
  }
})
```

**Impact:** Stabilizes HMR connection, prevents random disconnects and full reloads.

### Solution 3: Fix Font Flickering (FOUT)

**Option A: Preload the font (Recommended)**

Add to `app/app.vue`:

```vue
<script setup lang="ts">
useHead({
  // ... existing meta
  link: [
    { rel: 'icon', href: '/favicon.ico' },
    // Preload Public Sans font
    {
      rel: 'preload',
      href: 'https://fonts.gstatic.com/s/publicsans/v15/ijwGs572Xtc6ZYQws9YVwllKVG8qX1oyOymuFpm5ww0pX189fg.woff2',
      as: 'font',
      type: 'font/woff2',
      crossorigin: 'anonymous'
    }
  ]
})
</script>
```

**Option B: Use system fonts as primary (Eliminates FOUT entirely)**

In `app/assets/css/main.css`:

```css
@theme static {
  /* System fonts first for instant render, custom font as enhancement */
  --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI',
               'Public Sans', Roboto, 'Helvetica Neue', sans-serif;
}
```

**Option C: Use `font-display: optional`**

Configure Nuxt Fonts to use `optional` display which prevents FOUT by not swapping if font loads slowly:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  fonts: {
    defaults: {
      display: 'optional'
    }
  }
})
```

### Solution 4: Disable View Transitions (If Not Needed)

```ts
export default defineNuxtConfig({
  experimental: {
    viewTransition: false  // Disable if causing flicker
  }
})
```

**Impact:** Removes animation-based flickering during navigation.

### Solution 5: Clean Vite Cache Script

Add to `package.json`:

```json
{
  "scripts": {
    "dev:clean": "rm -rf node_modules/.vite && nuxt dev",
    "postpull": "rm -rf node_modules/.vite"
  }
}
```

**Impact:** Ensures clean state after git operations.

---

## Complete Recommended Configuration

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@nuxtjs/mdc',
    'nuxt-auth-utils'
  ],

  devtools: { enabled: false },

  devServer: {
    host: '127.0.0.1',
    port: 3000
  },

  css: ['~/assets/css/main.css'],

  // Font configuration
  fonts: {
    defaults: {
      display: 'swap',      // or 'optional' for no FOUT
      preload: true         // Preload fonts in <head>
    }
  },

  mdc: {
    headings: { anchorLinks: false },
    highlight: { shikiEngine: 'javascript' }
  },

  experimental: {
    viewTransition: false   // Disable if causing issues
  },

  compatibilityDate: '2024-07-11',

  nitro: {
    experimental: { openAPI: true },
    externals: { external: ['sharp'] }
  },

  vite: {
    // Pre-bundle heavy dependencies
    optimizeDeps: {
      include: [
        'ai',
        '@ai-sdk/vue',
        'drizzle-orm',
        'date-fns',
        '@nuxt/ui > @floating-ui/vue'
      ],
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
        usePolling: process.platform === 'win32',
        interval: 100
      }
    }
  },

  runtimeConfig: {
    // ... existing config
  },

  eslint: {
    // ... existing config
  }
})
```

---

## Quick Fixes (Minimal Changes)

If you want to apply minimal changes first:

### 1. Add optimizeDeps.include only:
```ts
vite: {
  optimizeDeps: {
    include: ['ai', '@ai-sdk/vue', 'drizzle-orm', 'date-fns']
  }
}
```

### 2. Add font preload in app.vue:
```vue
link: [
  { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: 'anonymous' }
]
```

### 3. Create clean script:
```json
"dev:clean": "rm -rf node_modules/.vite .nuxt && nuxt dev"
```

---

## Sources

- [Nuxt HMR Issues Discussion](https://github.com/nuxt/nuxt/discussions/8929)
- [Vite Dependency Optimization Options](https://vite.dev/config/dep-optimization-options)
- [Nuxt #27700 - Prevent optimized dependencies messages](https://github.com/nuxt/nuxt/discussions/27700)
- [Nuxt #25101 - optimizeDeps.include issue](https://github.com/nuxt/nuxt/issues/25101)
- [Nuxt #32564 - Windows HMR with Tailwind v4](https://github.com/nuxt/nuxt/issues/32564)
- [Nuxt #30725 - HMR broken with custom domain](https://github.com/nuxt/nuxt/issues/30725)
- [Nuxt Fonts Module - Loading causes flickering](https://github.com/nuxt/fonts/issues/181)
- [Nuxt UI Fonts Documentation](https://ui.nuxt.com/getting-started/fonts)
- [DebugBear - Fixing Layout Shifts from Web Fonts](https://www.debugbear.com/blog/web-font-layout-shift)
- [Walter Clayton - Nuxt HMR CSS Fix](https://blog.walterclayton.com/nuxt-hmr-css-fix/)

---

## Next Steps

1. Review this document
2. Decide which solutions to implement (recommend starting with Solution 1 + Solution 3 Option A)
3. Tell me to apply the changes
4. Test and iterate

