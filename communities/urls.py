from django.urls import path

from . import views

app_name = "communities"
urlpatterns = [
    path("", views.community_list, name="list"),
    path("new/", views.community_create, name="create"),
    path("<int:pk>/", views.community_detail, name="detail"),
    path("<int:pk>/rankings/", views.community_detail, {"tab": "rankings"}, name="rankings"),
    path("<int:pk>/bets/", views.community_detail, {"tab": "bets"}, name="bets"),
    path("<int:pk>/settings/", views.community_settings, name="settings"),
    path("<int:pk>/invite/", views.invite_member, name="invite"),
    path("<int:pk>/members/<int:user_id>/remove/", views.remove_member, name="remove_member"),
    path("<int:pk>/invitations/<int:inv_id>/cancel/", views.cancel_invitation, name="cancel_invitation"),
    path("<int:pk>/join/", views.join, name="join"),
    path("<int:pk>/leave/", views.leave, name="leave"),
]
