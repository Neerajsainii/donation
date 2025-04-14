#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Reset migrations completely if needed
rm -rf donation_app/migrations
mkdir -p donation_app/migrations
touch donation_app/migrations/__init__.py

# Create fresh migrations
python manage.py makemigrations donation_app
python manage.py migrate

# Create default categories
python manage.py create_default_categories 