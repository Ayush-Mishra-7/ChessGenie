# Prisma

This folder contains the Prisma schema for the project.

Quick commands (after installing dependencies):

```bash
# Install node deps

npm install

# Generate Prisma client
npm run prisma:generate

# Create initial migration (interactive)
npm run prisma:migrate
```

Make sure `DATABASE_URL` in your environment points to a Postgres database before running migrations.