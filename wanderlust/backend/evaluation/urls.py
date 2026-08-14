from django.urls import path

from .views import EvaluationResultsView, QuerySetView

urlpatterns = [
    path("", EvaluationResultsView.as_view(), name="evaluation-results"),
    path("queries/", QuerySetView.as_view(), name="evaluation-queries"),
]
