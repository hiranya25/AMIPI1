# Deployment Guide: AI Website Health Monitor

This guide provides step-by-step instructions for deploying the AI Website Health Monitor (FastAPI + Playwright + Static Frontend) to a production Linux server (e.g., Ubuntu 22.04 on AWS, DigitalOcean, or Linode).

## Prerequisites
- A Linux server (Ubuntu 20.04/22.04 recommended)
- Python 3.10 or higher installed
- Root or sudo access

---

## 1. Get the Code & Setup Environment

First, SSH into your server, navigate to where you want to host the app (e.g., `/var/www/`), and clone your GitHub repository:

```bash
# Example: Navigate to the web directory
sudo mkdir -p /var/www
cd /var/www

# Clone your repository from GitHub
sudo git clone https://github.com/your-username/your-repo-name.git amipi-monitor

# Take ownership of the directory
sudo chown -R $USER:$USER /var/www/amipi-monitor
cd amipi-monitor
```

Create a virtual environment and activate it:
```bash
python3 -m venv venv
source venv/bin/activate
```

## 2. Install Dependencies

Install the required Python packages from your `requirements.txt`:
```bash
pip install -r requirements.txt
```

### Install Playwright Browsers (Crucial for PDF Generation)
Because the app generates PDF reports using Playwright, you must install the Playwright browsers and their system dependencies:
```bash
playwright install --with-deps chromium
```

## 3. Configure Environment Variables

Create a `.env` file in the root of the project directory.

```bash
nano .env
```

Add your production configuration. Ensure you use your live API keys and correct SMTP details:

```ini
# .env
SITE_BASE_URL=https://amipi.com
AI_API_KEY=your_nvidia_api_key
AI_MODEL=nvidia/nemotron-3-ultra-550b-a55b
AI_API_BASE=https://integrate.api.nvidia.com/v1

# Email Settings (Example using Gmail App Passwords or SendGrid/AWS SES)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_RECIPIENTS=client@example.com, accounts2@amipi.com
```

## 4. Test the Application Locally

Before setting up background services, test that the app runs successfully:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open your browser and navigate to `http://your-server-ip:8000`. If the dashboard loads correctly, press `Ctrl+C` to stop the server.

---

## 5. Setup Systemd Service (Process Manager)

To ensure the FastAPI application runs continuously in the background and restarts automatically if the server reboots, configure a systemd service.

Create a new service file:
```bash
sudo nano /etc/systemd/system/amipi-monitor.service
```

Add the following configuration (replace `your_username` with your actual Linux user, e.g., `ubuntu` or `root`):

```ini
[Unit]
Description=Gunicorn instance to serve AI Website Health Monitor
After=network.target

[Service]
User=your_username
Group=www-data
WorkingDirectory=/var/www/amipi-monitor
Environment="PATH=/var/www/amipi-monitor/venv/bin"
# We use Uvicorn directly or Gunicorn with Uvicorn workers
ExecStart=/var/www/amipi-monitor/venv/bin/uvicorn app.main:app --host 127.0.0.0 --port 8000 --workers 2

[Install]
WantedBy=multi-user.target
```

Start and enable the service:
```bash
sudo systemctl start amipi-monitor
sudo systemctl enable amipi-monitor
sudo systemctl status amipi-monitor
```

---

## 6. Set Up Nginx Reverse Proxy (Optional but Highly Recommended)

To serve your application on standard HTTP (port 80) or HTTPS (port 443), use Nginx as a reverse proxy.

Install Nginx:
```bash
sudo apt update
sudo apt install nginx
```

Create a new Nginx configuration file:
```bash
sudo nano /etc/nginx/sites-available/amipi-monitor
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your_domain.com; # Replace with your domain or server IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/amipi-monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 7. Troubleshooting

- **PDF Generation Fails**: If PDFs are not generating, ensure Playwright dependencies are correctly installed using `playwright install-deps`.
- **Emails Not Sending**: Check your `SMTP_` variables in `.env`. If using Gmail, ensure you have generated an App Password, as standard passwords no longer work.
- **Checking Logs**: To see live logs and debugging information, check the systemd logs:
  ```bash
  sudo journalctl -u amipi-monitor.service -f
  ```

---

## Alternative: Deploy for Free on Render (Docker)

If you prefer a managed, free platform without configuring Linux yourself, you can deploy to Render using the included `Dockerfile`. Note that **Vercel** is not recommended because of the 50MB function size limit and the inability to run the continuous background schedule required for the weekly audits.

### Steps to Deploy on Render
1. Ensure the `Dockerfile` is pushed to your GitHub repository.
2. Go to [Render.com](https://render.com) and sign up/log in with GitHub.
3. Click **New +** -> **Web Service**.
4. Connect your GitHub repository.
5. In the settings:
   - **Environment:** Select **Docker** (Render will automatically detect the `Dockerfile`).
   - **Instance Type:** Select **Free** (512 MB RAM).
6. Expand **Advanced** and click **Add Environment Variable**. Paste all your variables from your `.env` file (e.g., `AI_API_KEY`, `SMTP_PASSWORD`).
7. Click **Create Web Service**. 

Render will automatically build the Docker container with the required Playwright headless browsers and give you a free `https://your-app.onrender.com` URL.

### ⚠️ Free Tier Caveats (Important!)

1. **The Sleeping Server Problem:** Render’s free tier goes to sleep after 15 minutes of inactivity. When the server is asleep, your background scheduler (APScheduler) **stops**, and weekly emails won't send.
   - **The Fix:** Create a free account at [cron-job.org](https://cron-job.org) and set it up to ping your Render URL (e.g., `https://your-app.onrender.com/health`) every 14 minutes. This tricks Render into staying awake forever.

2. **The Memory Problem:** Free tiers max out at **512MB RAM**. Because the app launches a full headless Chrome browser via Playwright to generate PDFs, you may occasionally encounter an Out Of Memory (OOM) error resulting in a crash. If this happens consistently, you will need to upgrade to Render's $7/mo plan or use the VPS method outlined at the beginning of this guide.
