from django.urls import path

from .views import AvailableModelsView, ModelComparisonView, RecommendationView

urlpatterns = [
    path("", RecommendationView.as_view(), name="recommendations"),
    path("compare/", ModelComparisonView.as_view(), name="recommendations-compare"),
    path("models/", AvailableModelsView.as_view(), name="recommendations-models"),
]
