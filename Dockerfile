FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
# Copy only the minimal public landing assets and server
COPY server.mjs ./server.mjs
COPY index.html styles.css hero.svg script.js ./
COPY animations ./animations
COPY vendor ./vendor
COPY fonts ./fonts
EXPOSE 5173
USER node
CMD ["node", "server.mjs"]
