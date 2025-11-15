from django.db import models

class Dataset(models.Model):
    file = models.FileField(upload_to='datasets/')          # uploaded CSV
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    summary = models.JSONField(blank=True, null=True)       # stores JSON summary

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.filename
