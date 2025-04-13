#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Apply migrations - Force recreation if tables are missing
python manage.py makemigrations donation_app --no-input
python manage.py migrate --no-input

# Create default categories
python manage.py create_default_categories 