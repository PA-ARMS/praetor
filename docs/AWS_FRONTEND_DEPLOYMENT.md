# AWS Frontend Deployment Guide

This guide provides step-by-step instructions for deploying the AKLAWMS frontend to AWS while keeping the backend at your local facility.

## Prerequisites

- AWS Account
- AWS CLI installed and configured
- Backend server running at your facility and accessible via internet
- Domain name (optional but recommended)

## Quick Start: S3 + CloudFront (Recommended)

### Step 1: Configure Frontend for Production

1. Navigate to the client directory:
   ```bash
   cd client
   ```

2. Create `.env.production` file:
   ```env
   VITE_API_URL=https://your-backend-domain.com
   ```
   Replace `your-backend-domain.com` with your actual backend URL.

3. Build the frontend:
   ```bash
   npm install  # If not already done
   npm run build
   ```

4. Verify the build output in `client/dist/` directory.

### Step 2: Create S3 Bucket

1. Go to AWS S3 Console
2. Create a new bucket:
   - Bucket name: `aklawms-frontend` (or your preferred name)
   - Region: Choose closest to your users
   - Block public access: Uncheck "Block all public access" (we'll use CloudFront)
   - Enable versioning (optional but recommended)

### Step 3: Upload Frontend Files

1. Upload all files from `client/dist/` to the S3 bucket
2. Make sure `index.html` is in the root of the bucket

### Step 4: Create CloudFront Distribution

1. Go to AWS CloudFront Console
2. Create distribution:
   - Origin Domain: Select your S3 bucket
   - Origin Access: Use Origin Access Control (recommended)
   - Viewer Protocol Policy: Redirect HTTP to HTTPS
   - Allowed HTTP Methods: GET, HEAD, OPTIONS (or GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE if needed)
   - Cache Policy: CachingDisabled (for development) or CachingOptimized (for production)
   - Default Root Object: `index.html`
   - Error Pages: Add custom error response for 403/404 to return `index.html` (for React Router)

3. Update S3 bucket policy to allow CloudFront access

### Step 5: Configure Custom Domain (Optional)

1. Request SSL certificate in AWS Certificate Manager (ACM)
2. Add custom domain in CloudFront distribution
3. Update DNS records to point to CloudFront distribution

### Step 6: Update Backend CORS

1. Get your CloudFront distribution URL (e.g., `https://d1234567890.cloudfront.net`)
2. Update `server/.env`:
   ```env
   CORS_ORIGINS=https://d1234567890.cloudfront.net,https://your-custom-domain.com
   ```
3. Restart backend server

## Alternative: EC2 Deployment

### Step 1: Launch EC2 Instance

1. Launch EC2 instance (Ubuntu 22.04 recommended)
2. Instance type: t3.small or t3.medium
3. Configure security group:
   - Allow HTTP (port 80) from 0.0.0.0/0
   - Allow HTTPS (port 443) from 0.0.0.0/0
   - Allow SSH (port 22) from your IP

### Step 2: Install Nginx

```bash
sudo apt update
sudo apt install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Step 3: Deploy Frontend Files

1. Build frontend locally (with `.env.production` configured)
2. Copy `client/dist/*` to EC2:
   ```bash
   scp -r client/dist/* ubuntu@your-ec2-ip:/var/www/html/
   ```
3. Or use git to clone and build on EC2

### Step 4: Configure Nginx

Edit `/etc/nginx/sites-available/default`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Optional: Add security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

Reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 5: Set Up HTTPS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

## Alternative: Elastic Beanstalk

### Step 1: Prepare Application

1. Build frontend with `.env.production` configured
2. Create deployment package structure:
   ```
   eb-app/
   ├── dist/
   │   └── (frontend build files)
   └── Procfile
   ```

3. Create `Procfile`:
   ```
   web: npx serve -s dist -l 8080
   ```

### Step 2: Deploy to Elastic Beanstalk

1. Install EB CLI: `pip install awsebcli`
2. Initialize EB: `eb init`
3. Create environment: `eb create`
4. Deploy: `eb deploy`

## Environment Variables

### Development
- `.env.local`: Local development with Vite proxy
- Leave `VITE_API_URL` empty to use proxy

### Production
- `.env.production`: AWS deployment
- Must set `VITE_API_URL` to your backend URL

## Build Commands

```bash
# Development
npm run dev

# Production build
npm run build

# Preview production build locally
npm run preview
```

## Testing Deployment

1. After deployment, test frontend URL
2. Verify API calls are going to correct backend
3. Check browser console for errors
4. Verify authentication flow works
5. Test all major features

## Troubleshooting

### 404 Errors on Routes

- Ensure Nginx/CloudFront is configured to serve `index.html` for all routes
- React Router needs this for client-side routing

### API Connection Errors

- Verify `VITE_API_URL` is set correctly in `.env.production`
- Check backend CORS configuration includes frontend domain
- Verify backend is accessible from internet

### CORS Errors

- Ensure backend `CORS_ORIGINS` includes your frontend domain
- Check protocol matches (http vs https)
- Verify credentials are configured correctly

## Cost Estimation

- **S3 + CloudFront**: ~$1-5/month for low traffic
- **EC2 t3.small**: ~$15/month
- **Elastic Beanstalk**: ~$20-30/month (includes EC2)

## Security Best Practices

1. Use HTTPS for both frontend and backend
2. Enable CloudFront security features
3. Configure proper CORS origins
4. Use environment variables for sensitive data
5. Enable AWS WAF if needed
6. Regularly update dependencies

