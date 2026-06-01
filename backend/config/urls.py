from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView, RedirectView
from django.views.static import serve as serve_static
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('admin', RedirectView.as_view(url='/admin/', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include('jobradar.urls')),
]
if settings.FRONTEND_DIST.exists():
    urlpatterns += [
        re_path(
            r'^static/assets/(?P<path>.*)$',
            serve_static,
            {'document_root': settings.FRONTEND_DIST / 'assets'},
        ),
        re_path(
            r'^static/(?P<path>favicon\.svg)$',
            serve_static,
            {'document_root': settings.FRONTEND_DIST},
        ),
    ]
    urlpatterns += [re_path(r'^(?!api/|admin/|static/).*$', TemplateView.as_view(template_name='index.html'))]
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
else:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
