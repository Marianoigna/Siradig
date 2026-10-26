from django.urls import path
from django.views.generic import TemplateView

app_name = "subscriptions"

urlpatterns = [
    # Placeholder para vista de planes (se implementará completamente en T6)
    path(
        "planes/",
        TemplateView.as_view(template_name="subscriptions/planes.html"),
        name="planes",
    ),
]
