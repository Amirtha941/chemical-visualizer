from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.UploadCSVView.as_view(), name="upload_csv"),
    path("datasets/", views.list_datasets, name="list_datasets"),
    path("report/<int:pk>/", views.generate_report, name="generate_report"),

    
]
