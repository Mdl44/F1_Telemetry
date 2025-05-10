#!/bin/bash
set -e

echo "F1 Telemetry Application Setup"
echo "------------------------------"

echo "Updating system packages..."
apt update && apt upgrade -y

echo "Installing dependencies..."
apt install -y python3-pip python3-dev libpq-dev postgresql postgresql-contrib nginx git

echo "Creating application directories..."
mkdir -p /var/www/f1telemetry/
mkdir -p /var/www/f1telemetry/media
mkdir -p /var/www/f1telemetry/static
mkdir -p /var/www/f1telemetry/analysis
mkdir -p /var/www/f1telemetry/analysis/quali_analysis
mkdir -p /var/www/f1telemetry/analysis/race_analysis
mkdir -p /var/www/f1telemetry/static_analysis

echo "Cloning repository from GitHub..."
git clone https://github.com/Mdl44/F1_Telemetry.git /tmp/F1_Telemetry

echo "Copying application files..."
cp -r /tmp/F1_Telemetry/* /var/www/f1telemetry/
rm -rf /tmp/F1_Telemetry

echo "Setting up Python virtual environment..."
python3 -m venv /var/www/f1telemetry/venv
/var/www/f1telemetry/venv/bin/pip install --upgrade pip
/var/www/f1telemetry/venv/bin/pip install -r /var/www/f1telemetry/requirements.txt

# Comment out all database setup commands to preserve existing database
# echo "Setting up PostgreSQL database..."
# sudo -u postgres psql -c "DROP DATABASE IF EXISTS f1_telemetry;"
# sudo -u postgres psql -c "DROP USER IF EXISTS madalin;"
# 
# sudo -u postgres psql -c "CREATE DATABASE f1_telemetry;"
# sudo -u postgres psql -c "CREATE USER madalin WITH PASSWORD 'madalin';"
# sudo -u postgres psql -c "ALTER ROLE madalin SET client_encoding TO 'utf8';"
# sudo -u postgres psql -c "ALTER ROLE madalin SET default_transaction_isolation TO 'read committed';"
# sudo -u postgres psql -c "ALTER ROLE madalin SET timezone TO 'UTC';"
# sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE f1_telemetry TO madalin;"
# 
# echo "Importing database schema..."
# sudo -u postgres psql -d f1_telemetry -f /var/www/f1telemetry/schema.sql

echo "Setting file permissions..."
chown -R www-data:www-data /var/www/f1telemetry/
chmod -R 755 /var/www/f1telemetry/

echo "Setting up Django application..."
cd /var/www/f1telemetry/

# /var/www/f1telemetry/venv/bin/python manage.py migrate --settings=F1_telemetry.settings_production

/var/www/f1telemetry/venv/bin/python manage.py collectstatic --noinput --settings=F1_telemetry.settings_production

# echo "Creating default admin user..."
# echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@example.com', 'adminpassword') if not User.objects.filter(username='admin').exists() else None" | /var/www/f1telemetry/venv/bin/python manage.py shell --settings=F1_telemetry.settings_production

echo "Setting up Gunicorn service..."
cp /var/www/f1telemetry/deployment/gunicorn.service /etc/systemd/system/
systemctl daemon-reload
systemctl start gunicorn
systemctl enable gunicorn

echo "Setting up Nginx web server..."
cp /var/www/f1telemetry/deployment/nginx.conf /etc/nginx/sites-available/f1telemetry
ln -sf /etc/nginx/sites-available/f1telemetry /etc/nginx/sites-enabled
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "✅ F1 Telemetry deployment complete!"
echo "Using existing database - no database changes were made"