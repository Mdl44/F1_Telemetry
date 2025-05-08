#!/bin/bash

apt update && apt upgrade -y

apt install -y python3-pip python3-dev libpq-dev postgresql postgresql-contrib nginx

mkdir -p /var/www/f1telemetry/

cp -r /tmp/F1_Telemetry/* /var/www/f1telemetry/

python3 -m venv /var/www/f1telemetry/venv
/var/www/f1telemetry/venv/bin/pip install -r /var/www/f1telemetry/requirements.txt

sudo -u postgres psql -c "CREATE DATABASE f1_telemetry;"
sudo -u postgres psql -c "CREATE USER madalin WITH PASSWORD 'madalin';"
sudo -u postgres psql -c "ALTER ROLE madalin SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE madalin SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE madalin SET timezone TO 'UTC';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE f1_telemetry TO madalin;"

adduser --disabled-password --gecos "" f1user
chown -R f1user:f1user /var/www/f1telemetry/

cd /var/www/f1telemetry/
source venv/bin/activate
python manage.py migrate --settings=F1_telemetry.settings_production
python manage.py collectstatic --noinput --settings=F1_telemetry.settings_production

cp /var/www/f1telemetry/deployment/gunicorn.service /etc/systemd/system/
systemctl start gunicorn
systemctl enable gunicorn

cp /var/www/f1telemetry/deployment/nginx.conf /etc/nginx/sites-available/f1telemetry
ln -s /etc/nginx/sites-available/f1telemetry /etc/nginx/sites-enabled
nginx -t
systemctl restart nginx

echo "Deployment complete!"