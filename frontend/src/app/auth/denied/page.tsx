import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function DeniedPage() {
  return (
    <div className="min-h-dvh flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm p-8 text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-destructive">Acceso Denegado</h1>
          <p className="text-muted-foreground text-sm">
            Tu cuenta no esta autorizada para acceder a esta aplicacion.
          </p>
        </div>

        <p className="text-xs text-muted-foreground">
          Si crees que esto es un error, contacta al administrador.
        </p>

        <Button asChild variant="outline">
          <Link href="/login">Volver al inicio</Link>
        </Button>
      </Card>
    </div>
  );
}
