/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // "standalone" gera um build self-contained em .next/standalone,
  // copiando só as dependências de produção realmente usadas — a
  // imagem Docker final fica muito menor do que copiar node_modules
  // inteiro (que inclui devDependencies como eslint, typescript etc).
  output: "standalone",
};
module.exports = nextConfig;
