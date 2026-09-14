from app.features.execution.tasks.core.registry import task


@task(name="dummy_discovered_task")
async def dummy_discovered_task():
    pass
