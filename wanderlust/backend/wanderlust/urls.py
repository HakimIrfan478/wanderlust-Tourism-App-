"""Root URL configuration for Wanderlust."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView


def api_root(_request):
    """A self-describing index, so the API can be explored from a browser."""
    return JsonResponse(
        {
            "service": "Wanderlust Tourism API",
            "version": "1.0",
            "description": (
                "Backend for a tourism management app that compares a "
                "transformer-based semantic recommender against a TF-IDF "
                "baseline over the same destination catalogue."
            ),
            "endpoints": {
                "auth": {
                    "register": "POST /api/auth/register/",
                    "login": "POST /api/auth/token/",
                    "refresh": "POST /api/auth/token/refresh/",
                    "verify": "POST /api/auth/token/verify/",
                    "profile": "GET|PATCH /api/auth/me/",
                    "favorites": "GET /api/auth/favorites/",
                    "toggle_favorite": "POST /api/auth/favorites/<destination_id>/",
                },
                "destinations": {
                    "list": "GET /api/destinations/?category=&country=&search=&tag=&max_cost=&sort=",
                    "detail": "GET /api/destinations/<id>/",
                    "facets": "GET /api/destinations/facets/",
                    "reviews": "GET|POST /api/destinations/<id>/reviews/",
                    "review_detail": "GET|PATCH|DELETE /api/destinations/reviews/<id>/",
                },
                "recommendations": {
                    "recommend": "POST|GET /api/recommendations/  (model=semantic|tfidf)",
                    "compare": "POST|GET /api/recommendations/compare/",
                    "models": "GET /api/recommendations/models/",
                },
                "evaluation": {
                    "results": "GET /api/evaluation/?full=1&refresh=1",
                    "query_set": "GET /api/evaluation/queries/",
                },
                "integrations": {
                    "weather": "GET /api/integrations/weather/?destination=<id>",
                    "country": "GET /api/integrations/country/?destination=<id>",
                    "context": "GET /api/integrations/context/?destination=<id>",
                },
            },
        },
        json_dumps_params={"indent": 2},
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    # Auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/auth/", include("accounts.urls")),
    # Domain
    path("api/destinations/", include("destinations.urls")),
    path("api/recommendations/", include("recommendations.urls")),
    path("api/evaluation/", include("evaluation.urls")),
    path("api/integrations/", include("integrations.urls")),
]
