import json
from typing import Any

from anyio import Path
from faststream.rabbit.annotations import ContextRepo

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.event_bus.utils import send_message
from saltbox_sdk.scheduler.messages import (
    RunTaskEventBusMessage,
    RunTaskResultEventBusMessage,
    RunTaskStatus,
    SyncTemplatesResponseEventBusMessage,
)


async def sync_scheduler_templates(templates_path: Path, service_name: str) -> None:
    templates: list[dict[str, Any]] = []

    logger.debug(f'Syncing scheduler templates from {templates_path}')

    async for template_path in templates_path.glob('*.json'):
        logger.debug(f'Loading template: {template_path}')

        async with await template_path.open('r') as f:
            templates.append(json.loads(await f.read()))

    logger.debug(f'Found templates: {[template["fun"] for template in templates]}')

    logger.debug(f'Syncing {len(templates)} templates ')
    for template in templates:
        await send_message(
            message=SyncTemplatesResponseEventBusMessage.model_validate(
                {
                    'sender': service_name,
                    'target': 'scheduler',
                    'task_target': template.get('target', service_name),
                    'fun': template['fun'],
                    'name': template['name'],
                    'json_schema': template.get('json_schema', {}),
                    'ui_schema': template.get('ui_schema', {}),
                }
            ),
            queue='scheduler_send_template',
        )
    logger.debug(f'Finished syncing {len(templates)} templates')


async def run_scheduled_task(message: RunTaskEventBusMessage, context: ContextRepo, scheduler_handlers: dict) -> None:
    result_status = RunTaskStatus.FAILURE

    if message.fun in scheduler_handlers:
        try:
            result_data = await scheduler_handlers[message.fun](message=message, context=context)

            result_status = RunTaskStatus.SUCCESS
        except Exception as e:
            logger.error(e)
            result_data = {'error': str(e)}
    else:
        result_data = {'error': f'Unknown function `{message.fun}`'}

    result_message = RunTaskResultEventBusMessage(
        sender=context.get('service_name'),
        target='scheduler',
        process_id=message.process_id,
        status=result_status,
        data=result_data,
    )

    await send_message(message=result_message, queue='scheduler_run_task_result')
