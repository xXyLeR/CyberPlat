# Multi-stage build: o estágio "builder" tem devDependencies inteiras
# (TypeScript, ESLint, Tailwind) mas NUNCA vai pra imagem final — só o
# output do "next build --output standalone" é copiado pro estágio de
# runtime. Isso reduz a superfície de ataque (menos pacotes = menos
# CVEs possíveis) e o tamanho da imagem.

FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-slim AS runtime
RUN useradd --uid 1000 --create-home webuser
WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER webuser
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
