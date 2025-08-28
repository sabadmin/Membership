# app/utils.py

from flask import request
from config import Config

def infer_tenant_from_hostname():
    """Infers the tenant ID from the current request's hostname."""
    current_hostname = request.host.split(':')[0]
    inferred_tenant = 'website' # Default
    for tenant_key in Config.TENANT_DATABASES.keys():
        if f"{tenant_key}.unfc.it" == current_hostname:
            inferred_tenant = tenant_key
            break
    return inferred_tenant

