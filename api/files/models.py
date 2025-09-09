from django.db import models


class FileUpload(models.Model):
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='uploads', null=True, blank=True)
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    content_type = models.CharField(max_length=100)
    size = models.IntegerField(default=0)
    ocr_text = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):  # pragma: no cover
        return f'Upload {self.id} ({self.content_type})'
