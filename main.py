"""
Lab Assistant - Main launcher
Ejecuta el backend (FastAPI) y el frontend (Vite) simultáneamente.

Uso:
    python main.py
"""
import asyncio
import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# Fix para Windows asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Rutas
ROOT_DIR = Path(__file__).parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

# Procesos globales para cleanup
processes = []


def check_npm_installed():
    """Verificar que npm esté instalado."""
    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True, shell=True)
        return True
    except:
        return False


def check_node_modules():
    """Verificar si node_modules existe, si no, ejecutar npm install."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("📦 Instalando dependencias del frontend (npm install)...")
        subprocess.run(
            ["npm", "install"],
            cwd=FRONTEND_DIR,
            shell=True,
            check=True
        )
        print("✅ Dependencias instaladas")


def cleanup(signum=None, frame=None):
    """Cerrar todos los procesos al salir."""
    print("\n🛑 Cerrando servicios...")
    for proc in processes:
        try:
            if sys.platform == "win32":
                proc.terminate()
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            pass
    sys.exit(0)


def main():
    """Ejecutar backend y frontend."""
    print("=" * 60)
    print("🧪 Lab Assistant AI - Iniciando servicios")
    print("=" * 60)
    
    # Registrar handler para Ctrl+C
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Verificar npm
    if not check_npm_installed():
        print("❌ Error: npm no está instalado. Instala Node.js primero.")
        sys.exit(1)
    
    # Instalar dependencias del frontend si es necesario
    check_node_modules()
    
    # Iniciar Backend
    print("\n🚀 Iniciando Backend (FastAPI) en http://localhost:8000")
    
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(BACKEND_DIR)
    
    if sys.platform == "win32":
        # En Windows, usar el script específico
        backend_proc = subprocess.Popen(
            [sys.executable, "run_windows.py"],
            cwd=BACKEND_DIR,
            env=backend_env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        backend_proc = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=BACKEND_DIR,
            env=backend_env,
            preexec_fn=os.setsid
        )
    processes.append(backend_proc)
    
    # Esperar un poco para que el backend inicie
    print("   Esperando que el backend inicie...")
    time.sleep(3)
    
    # Iniciar Frontend
    print("\n🎨 Iniciando Frontend (Vite) en http://localhost:5173")
    
    if sys.platform == "win32":
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=FRONTEND_DIR,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=FRONTEND_DIR,
            preexec_fn=os.setsid
        )
    processes.append(frontend_proc)
    
    print("\n" + "=" * 60)
    print("✅ Servicios iniciados!")
    print("")
    print("   📡 Backend API:  http://localhost:8000")
    print("   🌐 Frontend UI:  http://localhost:5173")
    print("")
    print("   El navegador Edge se abrió con la página del laboratorio.")
    print("   Inicia sesión si es necesario.")
    print("")
    print("   Presiona Ctrl+C para cerrar todo.")
    print("=" * 60)
    
    # Mantener el proceso principal vivo
    try:
        while True:
            # Verificar si algún proceso murió
            if backend_proc.poll() is not None:
                print("❌ Backend se cerró inesperadamente")
                cleanup()
            if frontend_proc.poll() is not None:
                print("❌ Frontend se cerró inesperadamente")
                cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
