# app/utils.py

from flask import request
from config import Config

def infer_tenant_from_hostname():
    current_hostname = request.host.split(':')[0]
    for tenant_key in Config.TENANT_DATABASES.keys():
        if f"{tenant_key}.unfc.it" == current_hostname:
            return tenant_key
    return 'website'  # Default tenant if no match is found