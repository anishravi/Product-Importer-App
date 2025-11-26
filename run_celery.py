#!/usr/bin/env python3
"""
Script to run Celery worker.
"""
from celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()

