from ..models import Metric


def get_all_metrics():
    return Metric.objects.all()


def get_metric(metric_name):
    return Metric.objects.filter(name__icontains=metric_name).first()


def get_metric_by_domain(domain):
    return Metric.objects.filter(domain__icontains=domain).first()

