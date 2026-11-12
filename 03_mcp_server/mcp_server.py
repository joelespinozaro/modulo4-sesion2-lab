"""Punto de entrada para `mcp dev` / `mcp run` / `mcp install`.

El CLI de `mcp` importa este archivo directamente (no como paquete) y solo
agrega la carpeta de este archivo a sys.path. Como `src/main.py` usa imports
absolutos (`from src.routes...`), necesita que la raíz del proyecto
(`03_mcp_server/`, no `src/`) esté en el path — por eso este shim vive aquí
y no dentro de `src/`.
"""

from src.main import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
