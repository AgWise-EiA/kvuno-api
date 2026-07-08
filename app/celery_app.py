import os

from celery import Celery

from dotenv import load_dotenv

load_dotenv()

celery_app = Celery('kvuno')

celery_app.config_from_object({
    'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    'task_default_queue': os.getenv('CELERY_TASK_DEFAULT_QUEUE', 'kvuno'),
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'task_track_started': True,
    'task_acks_late': True,
    'worker_prefetch_multiplier': 1,
    'broker_connection_retry_on_startup': False,
    'broker_connection_max_retries': 1,
})

celery_app.autodiscover_tasks(['app'])
