# 前端 Dockerfile（多阶段：Node 构建 + Nginx 托管，端口 80）
# ===== 阶段 1：构建静态文件 =====
FROM node:22-alpine AS builder

WORKDIR /app

# 先装依赖（利用层缓存，package.json 变化才重装）
COPY package.json package-lock.json* ./
# .npmrc 里 include=dev，确保 devDependencies（vite/vue-tsc）装上
RUN npm install

# 拷贝源码并构建（vite build 输出到 dist/）
COPY . .
RUN npm run build-only

# ===== 阶段 2：Nginx 托管 =====
FROM nginx:1.27-alpine

# 拷贝构建产物到 nginx 默认目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 拷贝 nginx 配置（反向代理 /api → backend:8000）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
