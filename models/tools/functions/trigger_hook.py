from provider.service_container import container


class TriggerHook:
    async def trigger_upload_image_event(self, caption = "") -> str:
        websocket = container.make('client_websocket_connection')
        
        await websocket.send_json(data={
            'event': 'trigger',
            'option': 'upload',
            'upload_type': 'image',
            'caption': caption
        })
        
        return "Wait for upload image by client user"