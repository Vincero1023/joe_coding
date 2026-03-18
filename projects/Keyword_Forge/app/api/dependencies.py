from app.analyzer.main import analyzer_module
from app.collector.main import collector_module
from app.expander.main import expander_module
from app.pipeline.main import pipeline_module
from app.selector.main import selector_module
from app.title_gen.main import title_generator_module


MODULE_REGISTRY = {
    "collect": collector_module,
    "expand": expander_module,
    "analyze": analyzer_module,
    "select": selector_module,
    "generate-title": title_generator_module,
    "pipeline": pipeline_module,
}


