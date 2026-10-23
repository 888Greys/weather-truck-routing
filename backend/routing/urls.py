from django.urls import path

from .views import GeocodeView, MetaView, PlanView

urlpatterns = [
    path("plan/", PlanView.as_view(), name="plan"),
    path("geocode/", GeocodeView.as_view(), name="geocode"),
    path("meta/", MetaView.as_view(), name="meta"),
]
