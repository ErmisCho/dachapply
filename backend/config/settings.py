import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-change-me')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('1','true','yes')
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()]

INSTALLED_APPS = [
 'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles',
 'rest_framework','corsheaders','jobradar'
]
MIDDLEWARE = [
 'django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','corsheaders.middleware.CorsMiddleware',
 'django.middleware.common.CommonMiddleware','config.middleware.NoCacheHtmlMiddleware','django.middleware.csrf.CsrfViewMiddleware','config.middleware.SplitAdminSessionMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware',
 'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware'
]
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates', BASE_DIR.parent/'frontend'/'dist'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'
DATABASES={'default': {'ENGINE': os.getenv('DB_ENGINE','django.db.backends.sqlite3'), 'NAME': os.getenv('DB_NAME', str(BASE_DIR/'db.sqlite3'))}}
if os.getenv('DATABASE_URL'):
    # PostgreSQL-compatible hook for later (install dj-database-url when needed).
    pass
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='Europe/Vienna'; USE_I18N=True; USE_TZ=True
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; STATICFILES_DIRS=[]
STATICFILES_STORAGE='whitenoise.storage.CompressedManifestStaticFilesStorage'
FRONTEND_DIST=BASE_DIR.parent/'frontend'/'dist'
if FRONTEND_DIST.exists(): STATICFILES_DIRS.append(FRONTEND_DIST)
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'], 'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated']}
CORS_ALLOWED_ORIGINS=[o.strip() for o in os.getenv('CORS_ALLOWED_ORIGINS','http://localhost:5173').split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS=True
LOGIN_URL='/login'
DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL','noreply@dachapply.local')
EMAIL_BACKEND=os.getenv('EMAIL_BACKEND','django.core.mail.backends.console.EmailBackend')
EMAIL_HOST=os.getenv('EMAIL_HOST','localhost')
EMAIL_PORT=int(os.getenv('EMAIL_PORT','25'))
EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS=os.getenv('EMAIL_USE_TLS','False').lower() in ('1','true','yes')
FRONTEND_URL=os.getenv('FRONTEND_URL','http://localhost:5173')
