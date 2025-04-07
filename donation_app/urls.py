# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.donate, name='home'),
    path('donate/', views.donate, name='donate'),
    path('thankyou/', views.thank_you, name='thank_you'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('life-member/', views.life_member, name='life_member'),
    path('process-membership/', views.process_membership, name='process_membership'),
]