import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagen de producción liviana (Cloud Run) — copia solo lo necesario para
  // correr `node server.js`, sin el resto de node_modules. Ver Dockerfile.
  output: "standalone",
};

export default nextConfig;
