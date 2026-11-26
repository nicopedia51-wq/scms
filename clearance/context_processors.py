def notifications(request):
    """Adds the unread-notification count to every template."""
    if request.user.is_authenticated:
        return {"unread_count": request.user.notifications.filter(is_read=False).count()}
    return {"unread_count": 0}
