from django.db import models


class ExportJob(models.Model):
    FORMAT_CHOICES = (
        ('md', 'Markdown'),
        ('pdf', 'PDF'),
        ('docx', 'DOCX'),
    )
    proposal = models.ForeignKey('proposals.Proposal', on_delete=models.CASCADE, related_name='export_jobs')
    format = models.CharField(max_length=8, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=16, default='pending')  # pending|done|error
    url = models.CharField(max_length=500, blank=True, default='')
    checksum = models.CharField(max_length=64, blank=True, default='')
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):  # pragma: no cover
        return f"ExportJob {self.id} {self.format} {self.status}"
