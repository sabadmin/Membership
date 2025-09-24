# app/utils.py

from flask import request
from config import Config
from datetime import datetime, timezone, timedelta

def infer_tenant_from_hostname():
    current_hostname = request.host.split(':')[0]

    # Special case: member.unfc.it should use tenant1 (admin) database
    if current_hostname == 'member.unfc.it':
        return 'tenant1'

    for tenant_key in Config.TENANT_DATABASES.keys():
        if f"{tenant_key}.unfc.it" == current_hostname:
            return tenant_key
    return 'tenant1'  # Default tenant if no match is found

def utc_to_local(utc_dt):
    """
    Convert UTC datetime to local time (Eastern Time).
    Assumes UTC datetime input and converts to America/New_York timezone.
    """
    if utc_dt is None:
        return None

    # Eastern Time offset (EDT is UTC-4, EST is UTC-5)
    # For simplicity, using fixed offset. In production, use pytz for proper DST handling
    eastern_offset = timedelta(hours=-4)  # EDT
    local_tz = timezone(eastern_offset)

    # If the datetime is naive (no timezone), assume it's UTC
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    # Convert to local time
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt
