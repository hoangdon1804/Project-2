# DEPLOYMENT GUIDE - Production Deployment

## 🚀 Deployment Checklist

### Pre-Deployment (Development Phase)

- [ ] All tests passing (unit tests, integration tests)
- [ ] No hardcoded credentials in code
- [ ] Database migrations ready
- [ ] API documentation complete (Swagger)
- [ ] Frontend build optimized
- [ ] Environment variables documented
- [ ] Error handling implemented
- [ ] Logging configured
- [ ] Security vulnerabilities scanned
- [ ] Load testing completed

---

## 📋 Environment Setup

### Backend Environment Variables

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=mysql+pymysql://username:password@hostname:3306/db_name

# JWT
SECRET_KEY=your-very-long-secret-key-minimum-32-characters-for-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Server
DEBUG=False
HOST=0.0.0.0
PORT=8000

# CORS
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Email (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/api.log
```

### Frontend Environment Variables

Create `.env.production` in frontend root:

```bash
REACT_APP_API_BASE=https://api.yourdomain.com
REACT_APP_ENVIRONMENT=production
REACT_APP_DEBUG=false
```

---

## 🐳 Docker Deployment

### Backend Dockerfile

Create `Dockerfile` in project root:

```dockerfile
# Use official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/docs || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

Create `frontend/Dockerfile`:

```dockerfile
# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built app to nginx
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  # MySQL Database
  mysql:
    image: mysql:8.0
    container_name: territory_mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME}
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - territory_network
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend API
  backend:
    build: .
    container_name: territory_backend
    environment:
      DATABASE_URL: mysql+pymysql://${DB_USER}:${DB_PASSWORD}@mysql:3306/${DB_NAME}
      SECRET_KEY: ${SECRET_KEY}
      ALLOWED_ORIGINS: ${ALLOWED_ORIGINS}
    ports:
      - "8000:8000"
    depends_on:
      mysql:
        condition: service_healthy
    networks:
      - territory_network
    restart: unless-stopped

  # Frontend
  frontend:
    build: ./frontend
    container_name: territory_frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - territory_network
    restart: unless-stopped

volumes:
  mysql_data:
    driver: local

networks:
  territory_network:
    driver: bridge
```

### Build and Run with Docker Compose

```bash
# Create .env file for compose
cat > .env << EOF
DB_ROOT_PASSWORD=secretpassword123
DB_NAME=territory_db
DB_USER=territory_user
DB_PASSWORD=territorypassword123
SECRET_KEY=your-long-secret-key-minimum-32-characters
ALLOWED_ORIGINS=https://yourdomain.com
EOF

# Build images
docker-compose build

# Run services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down
```

---

## ☁️ Cloud Deployment

### AWS Elastic Beanstalk

#### 1. Prepare Backend

Create `.ebextensions/python.config`:

```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: main:app
  aws:elasticbeanstalk:application:environment:
    PYTHONPATH: /var/app/current:$PYTHONPATH

commands:
  01_migrate:
    command: 'python -c "from models import Base, engine; Base.metadata.create_all(bind=engine)"'
    leader_only: true
```

Create `requirements.txt`:

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
mysql-connector-python==8.2.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pydantic==2.5.0
pydantic-settings==2.1.0
python-multipart==0.0.6
```

#### 2. Deploy Backend

```bash
# Install AWS EB CLI
pip install awsebcli

# Initialize EB application
eb init -p python-3.11 territory-api

# Create environment
eb create territory-api-env

# Set environment variables
eb setenv \
  DATABASE_URL=mysql+pymysql://user:pass@rds-endpoint:3306/dbname \
  SECRET_KEY=your-secret-key

# Deploy
eb deploy

# Check status
eb status

# View logs
eb logs
```

#### 3. AWS RDS for MySQL

```bash
# Via AWS Console:
# 1. Create RDS MySQL instance
# 2. Multi-AZ: Enabled
# 3. Storage: 20GB (auto-scaling enabled)
# 4. Backup retention: 7 days
# 5. Security group: Allow port 3306 from EB instances
# 6. Parameter group: utf8mb4 encoding
```

### Azure App Service

#### 1. Backend Setup

```bash
# Create App Service Plan
az appservice plan create \
  --name territory-plan \
  --resource-group mygroup \
  --sku B2 --is-linux

# Create App Service
az webapp create \
  --resource-group mygroup \
  --plan territory-plan \
  --name territory-api \
  --runtime "PYTHON|3.11"

# Configure deployment
az webapp deployment source config-zip \
  --resource-group mygroup \
  --name territory-api \
  --src-path backend.zip
```

#### 2. Database Setup

```bash
# Create MySQL Database for Azure
az mysql server create \
  --resource-group mygroup \
  --name territory-mysql \
  --admin-user dbadmin \
  --admin-password P@ssw0rd123
```

#### 3. Environment Configuration

```bash
# Set app settings
az webapp config appsettings set \
  --resource-group mygroup \
  --name territory-api \
  --settings \
    DATABASE_URL="mysql+pymysql://[user]:[pass]@[host]:3306/[db]" \
    SECRET_KEY="your-secret-key" \
    ALLOWED_ORIGINS="https://yourdomain.com"
```

### Heroku Deployment (Simpler, Traditional)

```bash
# Install Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Create app
heroku create territory-api

# Add buildpacks
heroku buildpacks:add heroku/python
heroku buildpacks:add heroku/nodejs -i 2

# Create database add-on
heroku addons:create jawsdb:kitefin

# Deploy
git push heroku main

# View logs
heroku logs --tail
```

---

## 🔒 Security Hardening

### Secrets Management

```bash
# Never commit secrets to git
# Use environment variables or secret managers

# AWS Secrets Manager
aws secretsmanager create-secret \
  --name territory-api-secrets \
  --secret-string '{"db_password":"...", "secret_key":"..."}'

# Azure Key Vault
az keyvault secret set \
  --vault-name territory-vault \
  --name DBPassword \
  --value "secure-password"
```

### SSL/TLS Certification

```bash
# Let's Encrypt with Certbot
certbot certonly --standalone -d yourdomain.com

# AWS Certificate Manager (ACM)
# Free, automatic renewal, integrates with ELB/CloudFront

# Configure in nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}
```

### Database Security

```sql
-- Create limited user for app
CREATE USER 'api_user'@'%' IDENTIFIED BY 'strong_password_123';
GRANT SELECT, INSERT, UPDATE, DELETE ON territory_db.* TO 'api_user'@'%';
FLUSH PRIVILEGES;

-- Enable SSL connections
ALTER USER 'api_user'@'%' REQUIRE SSL;

-- Create read-only user for backups
CREATE USER 'backup_user'@'localhost' IDENTIFIED BY 'backup_password';
GRANT SELECT ON territory_db.* TO 'backup_user'@'localhost';
```

### API Security

```python
# In main.py
from fastapi.middleware import TrustedHostMiddleware

# Add security headers
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["yourdomain.com", "www.yourdomain.com"]
)

# Add security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response

# Rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/login")
@limiter.limit("5/minute")
async def login(credentials: LoginSchema):
    pass
```

---

## 📊 Monitoring & Logging

### ELK Stack (Elasticsearch, Logstash, Kibana)

```yaml
# docker-compose for ELK
version: "3"
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
    environment:
      xpack.security.enabled: false
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.0.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    ports:
      - "5000:5000"

  kibana:
    image: docker.elastic.co/kibana/kibana:8.0.0
    ports:
      - "5601:5601"
```

### DataDog or New Relic

```python
# DataDog integration
from datadog import api
from datadog import initialize

options = {
    'api_key': 'YOUR_API_KEY',
    'app_key': 'YOUR_APP_KEY'
}

initialize(**options)

# Send event
from datadog.api.events import Event
Event.create(
    title="Territory API Deployed",
    text="Version 1.0 deployed to production",
    tags=["deployment", "production"]
)
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest

      - name: Run tests
        run: pytest tests/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Build Docker image
        run: docker build -t myregistry/territory-api:latest .

      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker push myregistry/territory-api:latest

      - name: Deploy to production
        run: |
          # Deploy command (Kubernetes, EB, etc.)
          kubectl set image deployment/territory-api \
            territory-api=myregistry/territory-api:latest \
            --record
```

---

## 📈 Performance Optimization

### Backend Optimization

```python
# Enable query caching
from sqlalchemy.orm import Session
from functools import lru_cache

@lru_cache(maxsize=128)
async def get_district_zones(district_id: int):
    return session.query(Zone).filter_by(district_id=district_id).all()

# Use connection pooling
from sqlalchemy.pool import NullPool

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # No connection pooling for serverless
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True
)
```

### Frontend Optimization

```bash
# Build optimization
npm run build

# Analyze bundle size
npm install --save-dev webpack-bundle-analyzer

# Code splitting
const AdminDashboard = React.lazy(() => import('./AdminDashboard'));

# Lazy loading
<Suspense fallback={<Loading />}>
  <AdminDashboard />
</Suspense>
```

### Database Optimization

```sql
-- Create indexes for common queries
CREATE INDEX idx_zone_district ON zones(district_id);
CREATE INDEX idx_territory_sales ON territories(sales_id);
CREATE INDEX idx_territory_district ON territories(district_id);
CREATE INDEX idx_zone_activity_zone ON zone_activities(zone_id);

-- Analyze tables
ANALYZE TABLE zones;
ANALYZE TABLE territories;
```

---

## 🔔 Alerting

### CloudWatch Alarms (AWS)

```bash
# CPU Alert
aws cloudwatch put-metric-alarm \
  --alarm-name territory-api-cpu-high \
  --alarm-description "Alert when API CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789:alert-topic
```

---

## 💾 Backup & Recovery

### Database Backup

```bash
# Automated backup with mysqldump
#!/bin/bash
BACKUP_DIR="/backups/mysql"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="territory_db_${DATE}.sql"

mysqldump \
  -u root -p$MYSQL_PASSWORD \
  territory_db > $BACKUP_DIR/$FILENAME

# Compress
gzip $BACKUP_DIR/$FILENAME

# Upload to S3
aws s3 cp $BACKUP_DIR/$FILENAME.gz s3://backup-bucket/

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### Database Restore

```bash
# From backup
mysql -u root -p territory_db < backup_2024_01_15.sql

# Or from S3
aws s3 cp s3://backup-bucket/backup_2024_01_15.sql.gz - | gunzip | mysql -u root -p territory_db
```

---

## 📋 Deployment Checklist

Before each deployment:

```
BACKEND:
[ ] All tests passing
[ ] No console.logs or debug code
[ ] Environment variables configured
[ ] Database migrations ready
[ ] Error handling complete
[ ] Logging configured
[ ] Security review passed
[ ] API documentation updated

FRONTEND:
[ ] All tests passing
[ ] No hardcoded URLs
[ ] Environment variables set
[ ] Build optimized (npm run build)
[ ] No console errors
[ ] Browser compatibility checked
[ ] Performance tested

DEPLOYMENT:
[ ] Backup database before deploy
[ ] Test on staging first
[ ] Certificate valid (SSL)
[ ] DNS updated
[ ] Health checks passing
[ ] Monitoring alerts active
[ ] Rollback plan ready
[ ] Post-deployment tests passing
```

---

## 🚨 Rollback Procedure

```bash
# Check current version
git log --oneline -5

# Rollback to previous version
git revert HEAD

# Or using Docker
docker pull myregistry/territory-api:previous-tag
docker tag myregistry/territory-api:previous-tag myregistry/territory-api:latest
docker push myregistry/territory-api:latest

# Or using Kubernetes
kubectl rollout undo deployment/territory-api
```

---

## 📞 Support

For deployment issues:

1. Check logs: `docker-compose logs backend`
2. Check database: `mysql -u root -p`
3. Check CORS: Browser DevTools → Network tab
4. Check API: `curl http://localhost:8000/docs`
5. Run health checks manually

---

**Last Updated:** 2024
**Deployment Version:** 1.0

Good luck with your deployment! 🚀
