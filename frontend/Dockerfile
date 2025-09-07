# Frontend Dockerfile for Vite React TypeScript
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Clean install with all dependencies and fix rollup issue
RUN rm -rf node_modules package-lock.json && npm install

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

# Copy built app from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]