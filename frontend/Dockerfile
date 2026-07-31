FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
ENV PORT=3701
EXPOSE 3701
CMD ["npm", "run", "start"]
