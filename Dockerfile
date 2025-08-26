FROM node:20-alpine
WORKDIR /app
COPY . .
ENV NODE_ENV=production
EXPOSE 5173
USER node
CMD ["node", "server.mjs"]
