# Environment Variables

This document describes the environment variables used in the TrustBill frontend application.

## Available Environment Variables

- `VITE_API_BASE_URL`: URL for the API backend endpoints that the frontend will connect to

## Setup Instructions

1. Copy `.env.example` to a new file named `.env`
2. Fill in the appropriate values for your environment
3. Restart the development server if it's already running

## Usage in Code

Access environment variables in your code using:

```typescript
// For Vite applications
import.meta.env.VITE_API_BASE_URL;

// Note: Only variables prefixed with VITE_ are exposed to your application code
```

## Production Deployment

For production deployment, set these environment variables in your hosting platform (Vercel, Netlify, AWS Amplify, etc.) rather than committing the `.env` file to your repository.
