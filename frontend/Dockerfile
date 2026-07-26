# Albee Stock 前端容器（開發模式：跑 Vite dev server，行為對齊 start_frontend.bat）
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# --host 0.0.0.0 才能讓容器外（host 端瀏覽器）連進來；預設只 bind 127.0.0.1
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
