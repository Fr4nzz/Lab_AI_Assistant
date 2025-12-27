'use client';

export default function OfflinePage() {
  return (
    <div className="min-h-dvh flex items-center justify-center bg-background p-4">
      <div className="text-center space-y-4 max-w-sm">
        <div className="text-6xl">📡</div>
        <h1 className="text-2xl font-bold">Sin conexion</h1>
        <p className="text-muted-foreground">
          No hay conexion a internet. Verifica tu conexion e intenta de nuevo.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Reintentar
        </button>
      </div>
    </div>
  );
}
