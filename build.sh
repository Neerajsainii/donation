#!/usr/bin/env bash
# exit on error
set -o errexit

# Print system information for debugging
echo "System information:"
echo "Python version: $(python --version)"
echo "PostgreSQL client version: $(pg_config --version || echo 'Not installed')"
echo "Current directory: $(pwd)"

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Print PostgreSQL connection info (without password)
if [ -n "$DATABASE_URL" ]; then
    echo "DATABASE_URL environment variable is set (not showing value for security)"
elif [ -n "$PGHOST" ]; then
    echo "PostgreSQL connection info: Host=$PGHOST, Port=$PGPORT, User=$PGUSER, Database=$PGDATABASE"
else
    echo "WARNING: No PostgreSQL connection information found. Using SQLite."
fi

# Reset migrations completely
echo "Resetting migrations..."
rm -rf donation_app/migrations
mkdir -p donation_app/migrations
touch donation_app/migrations/__init__.py

# Create fresh migrations
echo "Creating fresh migrations..."
python manage.py makemigrations donation_app

# Apply migrations
echo "Applying migrations..."
python manage.py migrate

# Create default categories
echo "Creating default categories..."
python manage.py create_default_categories

echo "Build script completed successfully!" 