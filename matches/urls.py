from django.urls import path

from . import views

app_name = "matches"
urlpatterns = [
    path("", views.match_list, name="list"),
    path("<int:pk>/", views.match_detail, name="detail"),
    path("tips/<int:pk>/react/", views.react, name="react"),
    path("my-bets/", views.my_bets, name="my_bets"),
    path("leagues/<str:code>/favourite/", views.toggle_favorite_league, name="favorite_league"),
]
