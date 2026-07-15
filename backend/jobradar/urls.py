from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router=DefaultRouter()
router.register('jobs', JobLeadViewSet, basename='jobs')
router.register('evaluations', EvaluationViewSet, basename='evaluations')
router.register('notes', NoteViewSet, basename='notes')
router.register('followups', FollowUpViewSet, basename='followups')

urlpatterns=[
 path('health/', health),
 path('auth/csrf/', csrf), path('auth/login/', login_view), path('auth/register/', register_view), path('auth/password-reset/', password_reset_request), path('auth/password-reset/confirm/', password_reset_confirm), path('auth/change-password/', change_password), path('auth/logout/', logout_view), path('auth/account/', delete_account), path('auth/me/', me), path('auth/friend-requests/', friend_requests), path('profile/', profile_settings),
 path('jobs/bulk-create/', bulk_create_jobs), path('public/submit/', public_submit), path('prompts/generate/', generate_prompt), path('prompts/enrich/', generate_enrichment_prompt), path('prompts/combined/', generate_combined_prompt), path('prompts/bulk-links/', generate_bulk_links_prompt), path('jobs/<int:job_id>/cv-generation/', cv_generation_preview), path('jobs/<int:job_id>/cv-generation/run/', generate_cv_documents), path('cv-generation/tasks/<str:task_id>/', cv_generation_status), path('cv-generation/tasks/<str:task_id>/download/', cv_generation_download), path('evaluations/import/', import_eval), path('stats/', stats),
 path('export/', export_user_data), path('import/', import_user_data),
 path('export/jobs.json', export_jobs_json), path('export/jobs.csv', export_jobs_csv), path('export/chatgpt-brief.md', export_chatgpt_brief),
 path('', include(router.urls)),
]
