# Frontend/Backend Split Deployment

This branch (`split-frontend-backend`) contains changes to support deploying the frontend on AWS while keeping the backend at your local facility.

## Quick Start

### For AWS Frontend Deployment

1. **Configure Frontend:**
   - See [AWS Frontend Deployment Guide](docs/AWS_FRONTEND_DEPLOYMENT.md)
   - Create `client/.env.production` with your backend URL:
     ```env
     VITE_API_URL=https://your-backend-domain.com
     ```
   - Build: `cd client && npm run build`

2. **Configure Backend:**
   - See [Backend Configuration for Remote Frontend](docs/BACKEND_REMOTE_FRONTEND.md)
   - Update `server/.env`:
     ```env
     CORS_ORIGINS=https://your-aws-frontend-domain.com
     ```

3. **Deploy:**
   - Deploy `client/dist` to AWS (S3+CloudFront, EC2, or Elastic Beanstalk)
   - Keep backend running at your facility

## Documentation

- [Frontend/Backend Split Guide](docs/FRONTEND_BACKEND_SPLIT.md) - Overview and architecture
- [AWS Frontend Deployment](docs/AWS_FRONTEND_DEPLOYMENT.md) - Step-by-step AWS deployment
- [Backend Remote Frontend Config](docs/BACKEND_REMOTE_FRONTEND.md) - Backend configuration

## Changes in This Branch

1. **Frontend:**
   - Updated `vite.config.js` with production build notes
   - Added documentation for environment variable configuration
   - Production builds now require `VITE_API_URL` to be set

2. **Backend:**
   - CORS configuration already supports remote frontends via `CORS_ORIGINS` environment variable
   - Documentation added for remote frontend setup

3. **Documentation:**
   - New deployment guides for split architecture
   - Updated main deployment guide with architecture options

## Testing

Before deploying to production:

1. Test locally with production build:
   ```bash
   cd client
   # Set VITE_API_URL in .env.production
   npm run build
   npm run preview
   ```

2. Verify backend CORS configuration:
   - Check backend logs for CORS configuration on startup
   - Test API calls from frontend

3. Test full deployment:
   - Deploy frontend to staging environment
   - Verify connection to backend
   - Test all major features

## Notes

- The Vite proxy is only used in development mode
- Production builds require `VITE_API_URL` to be set
- Backend must have proper CORS configuration for remote frontend
- Both frontend and backend should use HTTPS in production

