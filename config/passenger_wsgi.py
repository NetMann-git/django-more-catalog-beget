"""
WSGI config for project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os, sys
site_user_root_dir = '/home/m/moreug/dikar-sochi.rf/public_html'
sys.path.insert(0, site_user_root_dir + '/dikar-catalog')
sys.path.insert(1, site_user_root_dir + '/venv/lib/python3.11/site-packages')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.prod'
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
