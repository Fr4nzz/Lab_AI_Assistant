import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function AuthErrorPage() {
  return (
    <div className="min-h-dvh flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm p-8 text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-destructive">Error de Autenticacion</h1>
          <p className="text-muted-foreground text-sm">
            Ocurrio un error durante el proceso de inicio de sesion.
          </p>
        </div>

        <p className="text-xs text-muted-foreground">
          Por favor, intenta de nuevo. Si el problema persiste, contacta al administrador.
        </p>

        <Button asChild>
          <Link href="/login">Intentar de nuevo</Link>
        </Button>
      </Card>
    </div>
  );
}
