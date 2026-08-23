FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Server-side API base URL; containers reach the API service by name.
ENV NEXT_PUBLIC_API_BASE_URL=http://api:8000
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_PUBLIC_API_BASE_URL=http://api:8000
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm", "run", "start"]
