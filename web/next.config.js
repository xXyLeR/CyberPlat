/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // "standalone" só faz sentido para o Dockerfile (que roda `node
  // server.js` dentro do container, ver web/Dockerfile). Vercel e
  // Netlify têm seus próprios adaptadores para Next.js que já cuidam de
  // empacotar as rotas dinâmicas como funções serverless — "standalone"
  // ativo nessas plataformas quebra o roteamento e costuma resultar em
  // 404 nas páginas. Por isso isso só liga quando DOCKER_BUILD=1 (setado
  // explicitamente no Dockerfile), nunca por padrão.
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" } : {}),
};
module.exports = nextConfig;
