from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from django.views.generic import RedirectView

from accounts import views as accounts_views
from communities import views as community_views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="matches:list", permanent=False)),
    path("login/", accounts_views.SignInView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", accounts_views.register, name="register"),
    path("profile/", accounts_views.profile, name="profile"),
    path("ranking/", community_views.ranking_view, name="ranking"),
    path("matches/", include("matches.urls")),
    path("groups/", include("communities.urls")),
    path("admin/", admin.site.urls),
]
