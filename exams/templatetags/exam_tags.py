from django import template
from datetime import time, datetime

register = template.Library()

@register.filter
def split(value, arg):
    return value.split(arg)

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def format_time(time_obj):
    """Format time with special handling for 12 p.m."""
    if not time_obj:
        return ""
    
    # Check if it's a string or time object and convert accordingly
    if isinstance(time_obj, str):
        # For string input like "14:00:00"
        hours_str = time_obj[:2]
        minutes_str = time_obj[3:5]
        hours = int(hours_str)
        minutes = int(minutes_str)
    else:
        # For datetime.time objects
        hours = time_obj.hour
        minutes = time_obj.minute
    
    # AM/PM formatting
    period = "a.m." if hours < 12 else "p.m."
    
    # Convert to 12-hour format
    if hours == 0:
        display_hours = 12
    elif hours > 12:
        display_hours = hours - 12
    else:
        display_hours = hours
    
    # Format with or without minutes
    if minutes == 0:
        return f"{display_hours} {period}"
    else:
        return f"{display_hours}:{minutes:02d} {period}"

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    return dictionary.get(key)

@register.filter
def time_diff(end_time, start_time):
    """
    Calculate the difference in hours between two time objects
    """
    if not end_time or not start_time:
        return 0
    
    # Convert time objects to datetime objects for calculation
    end_dt = datetime.combine(datetime.today(), end_time)
    start_dt = datetime.combine(datetime.today(), start_time)
    
    # Calculate the difference in hours
    diff = end_dt - start_dt
    hours = diff.total_seconds() / 3600
    
    return round(hours, 1) 