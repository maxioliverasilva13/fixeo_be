from django.urls import re_path
from mensajeria import consumers as mensajeria_consumers

websocket_urlpatterns = [
    re_path(r'ws/mensajeria/(?P<room_name>\w+)/$', mensajeria_consumers.ChatConsumer.as_asgi()),
]