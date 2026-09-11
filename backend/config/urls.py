from django.contrib import admin
from django.http import HttpResponse
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
elif settings.DEBUG and settings.FRONTEND_URL and not settings.LAN_ACCESS:
    urlpatterns += [path('', RedirectView.as_view(url=settings.FRONTEND_URL, permanent=False))]
elif settings.LAN_ACCESS:
    # TASK-226: with LAN access on, / must never take the redirect above. FRONTEND_URL is
    # host-relative (http://localhost:5173 by default), so a phone that follows it resolves
    # `localhost` to ITSELF and gets nothing -- and it gets nothing while the bind and ALLOWED_HOSTS
    # both look perfectly correct, which is what makes that the expensive failure. Reaching here at
    # all means the branch above never ran, i.e. frontend/dist is missing, so there is no app to
    # serve; say that instead of sending the device somewhere that cannot work.
    # scripts/dachapply-local-runtime.cmd builds dist before it starts the server, so the normal LAN
    # path is the FRONTEND_DIST branch above: same-origin on :8000, no redirect, no cross-origin POST.
    urlpatterns += [path('', lambda request: HttpResponse(
        'DACHAPPLY_LAN_ACCESS is on but frontend/dist is missing, so there is no app to serve here.'
        ' Run `npm run build` in frontend/ and restart the server.',
        content_type='text/plain', status=503))]
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
else:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
