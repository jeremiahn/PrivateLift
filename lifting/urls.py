from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('log-set/', views.log_set, name='log_set'),
    path('profile/', views.profile_settings, name='profile_settings'),
    path('export/', views.export_data, name='export_data'),
    path('import/', views.import_data, name='import_data'),
    path('history/', views.history, name='history'),
    path('analytics/', views.analytics, name='analytics'),

    path('delete-set/<int:set_id>/', views.delete_set, name='delete_set'),
    path('update-set-type/<int:set_id>/', views.update_set_type, name='update_set_type'),

    # Custom Routine Templates
    path('load-template/', views.load_template, name='load_template'),
    path('save-template/', views.save_template, name='save_template'),
    path('delete-template/', views.delete_template, name='delete_template'),

    # Built-in Django password change view
    path('password/', auth_views.PasswordChangeView.as_view(
        template_name='lifting/password_change.html',
        success_url='/profile/'
    ), name='password_change'),
]
